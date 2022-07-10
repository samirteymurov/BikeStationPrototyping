import datetime
import os
import itertools
import logging
import time

import pytz
import zmq
import json
from dotenv import load_dotenv

from cloud.models import CurrentSpotState, ReservationStatus, SpotStateData

load_dotenv()

logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)

context = zmq.Context()
server = context.socket(zmq.REP)
print(os.getenv('bind_address'))
server.bind(os.getenv("bind_address"))


def convert_json_string_to_datetime(timestamp, with_ms):
    format = "%Y-%m-%d %H:%M:%S"
    if with_ms:
        format += ".%f"
    return datetime.datetime.strptime(
                    timestamp, format
                ).replace(tzinfo=pytz.utc)


for cycles in itertools.count():
    request = server.recv()
    request = json.loads(request.decode())
    #print(request)

    # process sensor data
    sensor_data = request.get("sensor_data")
    rejected_reservations = request.get("rejected_reservations")
    confirmed_reservations = request.get("confirmed_reservations")
    electricity_data = request.get("electricity_info")

    # iterate over current spot state and update state and reservations
    spot_states = CurrentSpotState.get_current_states()
    for spot_state in spot_states:
        spot_id = spot_state.spot_id
        # get latest data and set current state accordingly
        new_readings = sensor_data[str(spot_id)]
        if new_readings:
            latest_reading = sorted(new_readings, key=lambda d: d['datetime'], reverse=True)[0]
            is_occupied = latest_reading["is_occupied"]
            spot_state.update_occupied_and_battery_state(
                is_occupied=latest_reading["is_occupied"],
                battery_level=latest_reading["battery_level"]
            )
            # remove reservations for already removed bikes
            if not is_occupied and spot_state.reservation_status != ReservationStatus.no_reservation:
                spot_state.end_reservation()
        # update reservation state if responses have been received
        spot_reservation_id = spot_state.reservation_id
        if spot_reservation_id:
            reservation_id_key = str(spot_reservation_id)
            if reservation_id_key in confirmed_reservations.keys():
                logging.info(f"Reservation {reservation_id_key} has been confirmed.")
                valid_from_datetime = convert_json_string_to_datetime(
                    confirmed_reservations[reservation_id_key], True
                )
                spot_state.update_reservation_state(
                    reservation_status=ReservationStatus.reservation_confirmed,
                    reservation_id=spot_reservation_id,
                    valid_from=valid_from_datetime,
                )
            if spot_reservation_id in rejected_reservations:
                logging.info(f"Reservation {spot_reservation_id} for spot {spot_id} was not feasible.")
                spot_state.update_reservation_state(
                    reservation_status=ReservationStatus.no_reservation
                )
    logging.info("Successfully updated state.")

    # persist all received readings to db
    received_readings = []  # for monitoring purposes only
    for spot_id, data_list in sensor_data.items():
        for reading in data_list:
            received_readings.append(reading["reading_id"])
            SpotStateData(
                spot_id=spot_id,
                sensor_reading_id=reading["reading_id"],
                is_occupied=reading["is_occupied"],
                sensor_reading_timestamp=convert_json_string_to_datetime(reading["datetime"], False),
                battery_level=reading["battery_level"]
            )
    logging.info(f"Saved readings {received_readings}")

    # after making sure that all data have been processed send ok reply
    server.send(str(len(request)).encode())
