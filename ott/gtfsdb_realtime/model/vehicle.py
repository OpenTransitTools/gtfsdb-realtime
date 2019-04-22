import datetime

from geoalchemy2 import Geometry
from sqlalchemy import Column, Index, Integer, Numeric, String, DateTime
from sqlalchemy.sql import func, and_
from sqlalchemy.orm import deferred, object_session, relationship

from ott.gtfsdb_realtime.model.base import Base
from gtfsdb import Trip

import logging
log = logging.getLogger(__file__)


class Vehicle(Base):
    __tablename__ = 'rt_vehicles'

    vehicle_id = Column(String, nullable=False)
    license_plate = Column(String)

    lat = Column(Numeric(12,6), nullable=False)
    lon = Column(Numeric(12,6), nullable=False)
    bearing = Column(Numeric, default=0)
    odometer = Column(Numeric)
    speed = Column(Numeric)

    vehicle_id = Column(String)
    headsign = Column(String)
    trip_id = Column(String)
    block_id = Column(String)
    route_id = Column(String)
    direction_id = Column(String)
    service_id = Column(String)
    shape_id = Column(String)
    stop_id = Column(String)
    stop_seq = Column(Integer)
    status = Column(String)
    timestamp = Column(String)

    def __init__(self, agency, data):
        self.set_attributes(agency, data.vehicle)

    def set_attributes(self, agency, data):
        #import pdb; pdb.set_trace()
        self.agency = agency

        self.lat = round(data.position.latitude,  6)
        self.lon = round(data.position.longitude, 6)
        if hasattr(self, 'geom'):
            self.add_geom_to_dict(self.__dict__)

        self.bearing = data.position.bearing
        self.odometer = data.position.odometer
        self.speed = data.position.speed

        self.vehicle_id = data.vehicle.id
        self.headsign = data.vehicle.label
        self.trip_id = data.trip.trip_id
        self.route_id = data.trip.route_id
        self.stop_id = data.stop_id
        self.stop_seq = data.current_stop_sequence
        self.status = data.VehicleStopStatus.Name(data.current_status)
        self.timestamp = data.timestamp

    def add_trip_details(self, session):
        try:
            if self.trip_id:
                trip = Trip.query_trip(session, self.trip_id)
                if trip:
                    self.direction_id = trip.direction_id
                    self.block_id = trip.block_id
                    self.service_id = trip.service_id
                    self.shape_id = trip.shape_id
        except Exception as e:
            log.warning("trip_id '{}' not in the GTFS (things OUT of DATE???)".format(self.trip_id))

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
        if feed and feed.entity and len(feed.entity) > 0:
            super(Vehicle, cls).parse_gtfsrt_feed(session, agency, feed)

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
