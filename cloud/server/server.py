import datetime
import os
import itertools
import logging
import time

import pytz
import zmq
import json
from dotenv import load_dotenv

from cloud.models import CurrentSpotState, ReservationStatus, SpotStateData, CurrentElectricityState, ElectricityData

load_dotenv()

logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)

context = zmq.Context()
server = context.socket(zmq.REP)
logging.info('Listening to the incoming requests...')
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
        logging.info(f"Confirmed reservations: {list(confirmed_reservations.keys())}")
        logging.info(f"Rejected reservations: {rejected_reservations}")
        spot_reservation_id = spot_state.reservation_id

        # only update reservation state of spot, if reservation still pending on cloud part
        if spot_reservation_id:
            reservation_id_key = str(spot_reservation_id)
            if reservation_id_key in confirmed_reservations.keys():
                valid_from_datetime = convert_json_string_to_datetime(
                    confirmed_reservations[reservation_id_key], True
                )
                spot_state.update_reservation_state(
                    reservation_status=ReservationStatus.reservation_confirmed,
                    reservation_id=spot_reservation_id,
                    valid_from=valid_from_datetime,
                )
            if spot_reservation_id in rejected_reservations:
                spot_state.update_reservation_state(
                    reservation_status=ReservationStatus.no_reservation
                )

    # update electricity data state
    if electricity_data:
        latest_data = sorted(
            electricity_data.values(), key=lambda d: d['datetime'], reverse=True
        )[0]
        current_state = CurrentElectricityState.get_current_state()

        while current_state is None:
            logging.info('Database is empty. Waiting for some information')
            time.sleep(3)
            current_state = CurrentElectricityState.get_current_state()

        current_state.update_state(latest_data)
        # CurrentElectricityState(
        #     production=latest_data["production"],
        #     feed_in=latest_data["feed_in"],
        #     self_consumption=latest_data["self_consumption"],
        #     consumption_saving=latest_data["consumption_saving"],
        #     feed_in_revenue=latest_data["feed_in_revenue"],
        # ).save_or_update()

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

    # persist all received electricity data to db
    received_data_items = []  # for monitoring purposes only
    for item_id, electricity_data_item in electricity_data.items():
        received_data_items.append(item_id)
        ElectricityData(
            data_item_id=int(item_id),
            data_timestamp=convert_json_string_to_datetime(electricity_data_item["datetime"], False),
            production=electricity_data_item["production"],
            feed_in=electricity_data_item["feed_in"],
            self_consumption=electricity_data_item["self_consumption"],
            consumption_saving=electricity_data_item["consumption_saving"],
            feed_in_revenue=electricity_data_item["feed_in_revenue"],
        )
    logging.info(f"Saved electricity data items {received_data_items}")

    # after making sure that all data have been processed send ok reply
    server.send(str(len(request)).encode())
