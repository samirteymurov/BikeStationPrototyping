import os, itertools
import logging
import zmq
from dotenv import load_dotenv
load_dotenv()

from models import SpotSensorData, Status

logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)

REQUEST_TIMEOUT = 2500
server_url = os.getenv("server_address")

context = zmq.Context()

logging.info("Connecting to server...")
client = context.socket(zmq.REQ)
client.connect(server_url)

for sequence in itertools.count():
    queue_data = False
    # get first n data from db
    queued_readings = SpotSensorData.get_last_n_readings(10)
    encoded = SpotSensorData.encode_query(queued_readings)
    request = queued_readings

    logging.info("Sending (%s)", request)
    client.send(encoded)

    while True:
        if (client.poll(REQUEST_TIMEOUT) & zmq.POLLIN) != 0:
            reply = client.recv()
            if int(reply) == 6:  # sanity check with length of sent object
                logging.info("Server replied OK (%s)", reply)
                # status of sent records need to be set to "processed"
                SpotSensorData.set_to_processed(queued_readings[len(queued_readings)-1].read_id)
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
        logging.info("Resending (%s)", request)
        client.send(encoded)
