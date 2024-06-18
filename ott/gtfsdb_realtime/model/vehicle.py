import datetime

from geoalchemy2 import Geometry
from sqlalchemy import Column, Index, Integer, Numeric, String, DateTime, desc
from sqlalchemy.sql import func, and_
from sqlalchemy.orm import deferred, object_session, relationship

from ott.gtfsdb_realtime.model.base import Base
from gtfsdb import Trip

from cachetools import TTLCache

import logging
log = logging.getLogger(__file__)


class Vehicle(Base):
    __tablename__ = 'rt_vehicles'

    _route_cache = TTLCache(maxsize=10000, ttl=1200)

    vehicle_id = Column(String, nullable=False)
    license_plate = Column(String)

    lat = Column(Numeric(12, 6), nullable=False)
    lon = Column(Numeric(12, 6), nullable=False)
    bearing = Column(Numeric, default=0)
    odometer = Column(Numeric)
    speed = Column(Numeric)

    route_id = Column(String)
    route_type = Column(String)
    route_short_name = Column(String)
    route_long_name = Column(String)
    headsign = Column(String)

    vehicle_id = Column(String)
    trip_id = Column(String)
    block_id = Column(String)
    direction_id = Column(String)
    service_id = Column(String)
    shape_id = Column(String)
    stop_id = Column(String)
    stop_seq = Column(Integer)
    status = Column(String)
    timestamp = Column(String)

    def __init__(self, agency, data=None):
        super(Vehicle, self).__init__()
        self.agency = agency
        if data and data.vehicle:
            self.set_attributes(data.vehicle)

    def set_attributes(self, data):
        self.lat = round(data.position.latitude,  6)
        self.lon = round(data.position.longitude, 6)
        if hasattr(self, 'geom'):
            self.add_geom_to_dict(self.__dict__)

        self.bearing = data.position.bearing
        self.odometer = data.position.odometer
        self.speed = data.position.speed

        self.route_id = data.trip.route_id
        self.route_long_name = data.trip.route_id
        self.route_short_name = data.trip.route_id
        self.route_type = "TRANSIT"
        self.headsign = data.vehicle.label

        self.vehicle_id = data.vehicle.id
        self.trip_id = data.trip.trip_id
        self.stop_id = data.stop_id
        self.stop_seq = data.current_stop_sequence
        self.status = data.VehicleStopStatus.Name(data.current_status)
        self.timestamp = data.timestamp

    def add_trip_details(self, session):
        # import pdb; pdb.set_trace()
        try:
            if self.trip_id:
                trip = Trip.query_trip(session, self.trip_id)
                if trip:
                    self.direction_id = trip.direction_id
                    self.block_id = trip.block_id
                    self.service_id = trip.service_id
                    self.shape_id = trip.shape_id
                    self.add_route_details(trip)
        except Exception as e:
            log.warning("trip_id '{}' not in the GTFS (things OUT of DATE???)".format(self.trip_id))

    def add_route_details(self, trip):
        """
        add (cached) route data to this object
        @see add_trip_details()
        """
        try:
            route = self._route_cache.get(trip.trip_id)
            if route is None:
                route = {
                    'n': trip.route.route_name,
                    's': trip.route.make_route_short_name(trip.route),
                    't': trip.route.type.otp_type
                }
                self._route_cache[trip.trip_id] = route

            self.route_long_name = route['n']
            self.route_short_name = route['s']
            self.route_type = route['t']
        except Exception as e:
            log.warning("route data for trip {} threw an exception:\n{}".format(self.trip_id, e))

    @classmethod
    def add_geometry_column(cls, srid=4326):
        cls.geom = Column(Geometry(geometry_type='POINT', srid=srid))

    @classmethod
    def add_geom_to_dict(cls, row, srid=4326):
        row['geom'] = 'SRID={0};POINT({1} {2})'.format(srid, row['lon'], row['lat'])

    @classmethod
    def clear_tables(cls, session, agency):
        """
        clear out the positions and vehicles tables
        """
        session.query(Vehicle).filter(Vehicle.agency == agency).delete()

    @classmethod
    def parse_gtfsrt_feed(cls, session, agency, feed):
        timestamp = None
        if feed and feed.entity and len(feed.entity) > 0:
            timestamp = super(Vehicle, cls).parse_gtfsrt_feed(session, agency, feed)
            if timestamp:
                VehiclesTimestamp.update(session, agency, timestamp)

    @classmethod
    def parse_gtfsrt_record(cls, session, agency, record, timestamp):
        """ create or update new Vehicles and positions
            :return Vehicle object
        """
        v = Vehicle(agency, record)
        v.add_trip_details(session)
        session.add(v)
        #import pdb; pdb.set_trace()
        return v


# TODO: make this generic
class VehiclesTimestamp(Base):
    __tablename__ = 'rt_vehicles_timestamp'
    timestamp = Column(Integer)

    def __init__(self, agency, timestamp, id=None):
        if id:
            self.id = id
        self.agency = agency
        self.timestamp = timestamp

    def toUtc(self):
        return datetime.datetime.utcfromtimestamp(self.timestamp)

    @classmethod
    def update(cls, session, agency, timestamp):
        vt = cls(agency, timestamp, 1)
        session.merge(vt)

    @classmethod
    def query(cls, session, all=False, latest_first=True):
        q = session.query(cls)
        q = q.order_by(desc(cls.timestamp)) if latest_first else q.order_by(cls.timestamp)
        ret_val = q.all() if all else q.one()
        return ret_val

