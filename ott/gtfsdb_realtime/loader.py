from ott.gtfsdb_realtime.model.database import Database
from ott.gtfsdb_realtime.model.base import Base

from ott.utils.compat_2_to_3 import *
from ott.utils.parse.cmdline import gtfs_cmdline
from ott.utils.parse.cmdline import db_cmdline
from ott.utils.config_util import ConfigUtil
from ott.utils import string_utils
from ott.utils import num_utils
from ott.utils import db_utils
from ott.utils import gtfs_utils

import time
import logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__file__)


def load_agency_feeds(session, agency_id, alerts_url=None, trips_url=None, vehicles_url=None, nextbus_url=None, durr=None, freq=None):
    """
    This is a main entry for loading one or more GTFS-RT feeds ...
    """
    ret_val = True

    # import pdb; pdb.set_trace()
    freq = num_utils.to_int(freq)
    durr = num_utils.to_int(durr)
    start = int(time.time())

    i = 0
    while True:
        i = i + 1
        if alerts_url:
            r = load_gtfsrt_feed(session, agency_id, alerts_url)
            if not r:
                ret_val = False

        if trips_url:
            r = load_gtfsrt_feed(session, agency_id, trips_url)
            if not r:
                ret_val = False

        if vehicles_url:
            r = load_gtfsrt_feed(session, agency_id, vehicles_url)
            if not r:
                ret_val = False

        elapse = int(time.time()) - start
        if durr:
            if durr - elapse <= 0:
                log.info("EXITING: process ran for {} seconds (e.g., specified duration of {} secs)".format(elapse, durr))
                break
            else:
                log.info("CONTINUING: process has run for {} seconds of {} duration (iteration {})".format(elapse, durr, i))

        if freq:
            log.info("sleeping for {} seconds (iteration {} ... process has been running for {} seconds)".format(freq, i, elapse))
            time.sleep(freq)
        else:
            break

    return ret_val


def load_gtfsrt_feed(session, agency_id, feed_url, clear_tables_first=True):
    """
    this is a main entry for loading a single GTFS-RT feed
    the logic here will grab a GTFS-RT feed, and store it in a database
    """
    feed = grab_feed(feed_url)
    feed_type = Base.get_feed_type(feed)
    if feed_type:
        ret_val = store_feed(session, agency_id, feed_type, feed, clear_tables_first)
    else:
        log.warning("not sure what type of data we got back from {}".format(feed_url))
        ret_val = False
    return ret_val


def grab_feed(feed_url):
    """
    download a feed from a url
    :see: https://developers.google.com/transit/gtfs-realtime/examples/
    """
    from google.transit import gtfs_realtime_pb2

    log.info("calling GTFS-RT feed url: {}".format(feed_url))
    feed = gtfs_realtime_pb2.FeedMessage()
    response = urllib.request.urlopen(feed_url)
    feed.ParseFromString(response.read())
    return feed


def store_feed(session, agency_id, feed_type, feed, clear_tables_first):
    """
    put a gtfs-rt feed into a database
    """
    ret_val = False

    try:
        # step 1: create a savepoint
        session.begin_nested()

        # step 2: clear content from existing tables
        if clear_tables_first:
            feed_type.clear_tables(session, agency_id)

        # step 3: add gtfsrt data to db
        feed_type.parse_gtfsrt_feed(session, agency_id, feed)

        """
        # development junk
        if feed_type:
            from ott.gtfsdb_realtime.control.nextbus.controller import Controller
            c = Controller()
            c.to_orm(session)
        """

        # step 4: commit the session
        session.commit()
        session.commit()  # think I need 2 commits due to session create + begin_nested being created above.
        session.flush()

        ret_val = True
    except Exception as e:
        # step 5: something bad happened ... roll back to our old savepoint
        log.error(e)
        session.rollback()
        session.rollback()
        session.commit()
        session.flush()

    return ret_val


def load_vehicles(section='gtfs_realtime'):
    """
    insert a GTFS feed into configured db
    """
    args = db_cmdline.db_parser('bin/gtfsrt-vehicles-load', do_parse=True, url_required=False, add_misc=True)
    config = ConfigUtil.factory(section=section)
    feed = config.get_json('feeds')[0]
    url = config.get('db_url')
    ret_val = load_feeds_via_config(feed, url, do_trips=False, do_alerts=False, create_db=args.create, durr=args.durr, freq=args.freq)
    return ret_val


def load_feeds_via_config(feed, db_url, do_trips=True, do_alerts=True, do_vehicles=True, is_geospatial=True, create_db=False, durr=None, freq=None):
    """
    insert a GTFS feed into configured db
    """
    ret_val = True

    # step 1: agency and schema
    agency_id = feed.get('agency_id')
    schema = feed.get('schema', agency_id.lower())

    # step 2: get urls to this feed's
    trips_url = gtfs_utils.get_realtime_trips_url(feed) if do_trips else None
    alerts_url = gtfs_utils.get_realtime_alerts_url(feed) if do_alerts else None
    vehicles_url = gtfs_utils.get_realtime_vehicles_url(feed) if do_vehicles else None

    # step 3: load them there gtfs-rt feeds
    # import pdb; pdb.set_trace()
    session = Database.make_session(db_url, schema, is_geospatial, create_db)
    try:
        log.info("loading gtfsdb_realtime db {} {}".format(db_url, schema))
        ret_val = load_agency_feeds(session, agency_id, trips_url, alerts_url, vehicles_url, "DO NB", durr, freq)
    except Exception as e:
        log.error("DATABASE ERROR : {}".format(e))
        ret_val = False
    finally:
        # note - when loading multiple feeds, closing then opening new session messes up 2nd agency / schema load with this exeption
        #        sqlalchemy.exc.InvalidRequestError: Implicitly combining column (py so messy, bro?)
        # Database.close_session(session)
        session = None

    return ret_val


def load_feeds_via_cmdline(api_key_required=True, agency_required=True, api_key_msg="Get a TriMet API Key at http://developer.trimet.org/appid/registration"):
    """ this main() function will call TriMet's GTFS-RT apis by default (as and example of how to load the system) """
    args = gtfs_cmdline.gtfs_rt_parser(api_key_required=api_key_required, api_key_msg=api_key_msg, agency_required=agency_required)

    schema = string_utils.get_val(args.schema, args.agency_id.lower())
    url = db_utils.check_localhost(args.database_url)
    session = Database.make_session(url, schema, args.is_geospatial, args.create)

    api_key = string_utils.get_val(args.api_key, '<your key here>')
    aurl = string_utils.get_val(args.alerts_url, 'http://developer.trimet.org/ws/V1/FeedSpecAlerts/includeFuture/true/appId/' + api_key)
    turl = string_utils.get_val(args.trips_url, 'http://developer.trimet.org/ws/V1/TripUpdate/appId/' + api_key)
    vurl = string_utils.get_val(args.vehicles_url, 'http://developer.trimet.org/ws/gtfs/VehiclePositions/appId/' + api_key)
    no_errors = load_agency_feeds(session, args.agency_id, aurl, turl, vurl)
    if no_errors:
        log.info("Thinking that loading went well...")
    else:
        log.info("Errors Loading???")


def main():
    load_feeds_via_cmdline()


if __name__ == '__main__':
    main()

