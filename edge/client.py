import os, itertools
import logging
import time
import zmq
from dotenv import load_dotenv
from models import SpotSensorData, Status

load_dotenv()
logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)

REQUEST_TIMEOUT = 2500
server_url = os.getenv("server_address")
context = zmq.Context()

logging.info("Connecting to server...")
client = context.socket(zmq.REQ)
client.connect(server_url)

for sequence in itertools.count():
    # TODO add reservation confirmations/rejections to message
    time.sleep(5)
    # get oldest n sensor readings from db
    queued_readings = SpotSensorData.get_oldest_n_readings(10)
    if len(queued_readings) == 0:
        logging.info("No new sensor reading to be sent. Waiting...")
        continue

    encoded = SpotSensorData.encode_query(queued_readings)

    logging.info("Sending (%s)", encoded)
    client.send(encoded)

    while True:
        if (client.poll(REQUEST_TIMEOUT) & zmq.POLLIN) != 0:
            reply = client.recv()
            if int(reply) == 5:  # sanity check with length of sent object
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
        logging.info("Resending (%s)", encoded)
        client.send(encoded)
