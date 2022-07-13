import json
import os, itertools
import logging
import time
import zmq
from dotenv import load_dotenv
from models import SpotSensorData, Status, Reservation, ElectricityData

load_dotenv()
logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)

REQUEST_TIMEOUT = 2500
server_url = os.getenv("server_address")
context = zmq.Context()

logging.info("Connecting to server...")
client = context.socket(zmq.REQ)
client.connect(server_url)

for sequence in itertools.count():
    # get oldest 10 sensor readings from db
    queued_readings = SpotSensorData.get_oldest_n_readings(10)
    # get oldest 10 electricity data items from db
    queued_electricity_data = ElectricityData.get_oldest_n_readings(10)

    # get processed reservations from db
    confirmed_reservations = Reservation.get_confirmed_reservation_requests()
    rejected_reservations = Reservation.get_rejected_reservation_requests()
    if (
            len(queued_readings) == 0
            and len(confirmed_reservations) == 0
            and len(rejected_reservations) == 0
            and len(queued_electricity_data) == 0
    ):
        logging.info("No new data to be sent. Waiting...")
        time.sleep(1)
        continue

    sensor_data_dict = SpotSensorData.make_query_dictionary(queued_readings)
    electricity_data_dict = ElectricityData.make_query_dictionary(queued_electricity_data)
    confirmed_reservations_dict = Reservation.make_confirmed_reservations_dict(confirmed_reservations)
    rejected_reservations_list = [reservation.reservation_id for reservation in rejected_reservations]

    message_dict = {
        "sensor_data": sensor_data_dict,
        "rejected_reservations": rejected_reservations_list,
        "confirmed_reservations": confirmed_reservations_dict,
        "electricity_info": electricity_data_dict,
    }
    encoded = json.dumps(message_dict, default=str).encode()

    logging.info("Sending sensor data, electricity info and reservation responses.")
    client.send(encoded)

    while True:
        if (client.poll(REQUEST_TIMEOUT) & zmq.POLLIN) != 0:
            reply = client.recv()
            if int(reply) == 4:  # sanity check with length of sent object
                logging.info("Server replied OK")
                # status of sent records need to be set to "processed"
                if len(queued_readings) > 0:
                    SpotSensorData.set_to_processed(queued_readings[len(queued_readings)-1].read_id)
                if len(queued_electricity_data) > 0:
                    ElectricityData.set_to_processed(queued_electricity_data[len(queued_electricity_data)-1].data_item_id)
                for reservation in rejected_reservations:
                    reservation.update_response_sent()
                for reservation in confirmed_reservations:
                    reservation.update_response_sent()
                break
            else:
                logging.error("Malformed reply from server: %s", reply)
                continue
        # {REQUEST_TIMEOUT} seconds passed, but no results yet
        logging.warning("No response from server")
        # Socket is confused. Close and remove it.
        client.setsockopt(zmq.LINGER, 0)
        client.close()
        logging.info("Reconnecting to server…")
        # Create new connection
        client = context.socket(zmq.REQ)
        client.connect(server_url)
        logging.info("Resending sensor data, electricity info and reservation responses.")
        client.send(encoded)
