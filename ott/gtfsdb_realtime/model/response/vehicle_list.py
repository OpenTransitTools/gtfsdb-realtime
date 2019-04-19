"""
this response format is one that is modeled after the stop and route responses from OpenTripPlanner
OTP doesn't have vehicle data, but I wanted to model this rt vehicle response on OTP TI, so that
it fits with a style of services from that system
"""
import datetime
import logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__file__)

"""
    "id": "1111-trimet",
    "vehicle": "1111",
    "mode": "BUS",
    "destination": "20  Burnside\/Stark to Gresham TC via Portland City ter",
    "timestamp": 1555555555,

    "lat": 45.5092,
    "lon": -122.773568,
    "heading": 104,
    "lastUpdate": 5,
    "realtimeState": "SCHEDULED",
    "stopId": "1",
    "stopSeq": "1",

    "agencyName": "TriMet",
    "agencyId": "TRIMET",
    "routeShortName": "20",
    "routeId": "20",
    "directionId": "1",
    "tripId": "8983916",
    "blockId": "2074",
    "patternId": "111",
    "serviceId": "111",
    "serviceDay": 1555052400

"""

class Vehicle(object):
    rec = {}

    def __init__(self, vehicle, index):
        self.make_vehicle_record(vehicle, index)

    def make_vehicle_record(self, v, i, agency='trimet'):
        """
        :return a vehicle record
        """
        # import pdb; pdb.set_trace()

        # note: we might get either Vehicle or Position objects here based on how the query happened
        #       so we first have to get both the position and the vehicle objects
        from ..vehicle_position import VehiclePosition
        if isinstance(v, VehiclePosition):
            position = v
            v = position.vehicle[0]
        else:
            position = v.positions[0]

        self.rec = {
            "id": "{}-{}".format(v.vehicle_id, agency),
            "lon": -000.111,
            "lat": 000.111,
            "heading": float(position.bearing),
            "vehicleId": v.vehicle_id,
            "destination": position.headsign,

            "agencyId": position.agency,
            "routeId": position.route_id,
            "tripId": position.trip_id,
            "shapeId": position.shape_id,
            "directionId": position.direction_id,
            "blockId": position.block_id,
            "stopId": position.stop_id,
            "stopSequence": position.stop_seq,

            "status": position.status,
            "seconds": 0,
            "reportDate": "11.11.2111 11:11 pm"
        }
        self.set_coord(float(position.lat), float(position.lon))
        self.set_time(float(position.timestamp))

    def set_coord(self, lat, lon):
        self.rec['lat'] = lat
        self.rec['lon'] = lon

    def set_time(self, time_stamp):
        t = datetime.datetime.fromtimestamp(time_stamp)
        pretty_date_time = t.strftime('%x %I:%M %p').replace(" 0", " ")
        diff = datetime.datetime.now() - t
        self.rec['seconds'] = diff.seconds
        self.rec['reportDate'] = str(pretty_date_time)


class VehicleListResponse(object):
    records = []

    def __init__(self, vehicles):
        for i, v in enumerate(vehicles):
            v = Vehicle(v, i)
            self.records.append(v)

    @classmethod
    def make_response(cls, vehicles, pretty=True):
        vl = VehicleListResponse(vehicles)
        return vl.records