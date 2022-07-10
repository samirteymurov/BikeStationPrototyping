import json
import os, itertools
import logging
import random
from time import sleep

import zmq
from dotenv import load_dotenv

from cloud.models import ReservationRequest

load_dotenv()
logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)

REQUEST_TIMEOUT = 2500
MAX_NUMBER_OF_RETRIES = 5
server_url = os.getenv("server_address")
context = zmq.Context()

logging.info("Connecting to server...")
client = context.socket(zmq.REQ)
client.connect(server_url)

for sequence in itertools.count():
    sleep(3)
    current_electricity_price_per_kwh = round(random.uniform(0.27, 0.68), 4)
    pending_reservations = ReservationRequest.get_pending_reservations()
    reservations_dict = ReservationRequest.make_query_dictionary(pending_reservations)

    message_dict = {
        "current_market_price": current_electricity_price_per_kwh,
        "reservations": reservations_dict,
    }
    encoded_message = json.dumps(message_dict, default=str).encode()
    logging.info("Sending current market price and open reservations.")

    client.send(encoded_message)

    retries = 0

    while True:
        if (client.poll(REQUEST_TIMEOUT) & zmq.POLLIN) != 0:
            reply = client.recv()
            #print(reply)
            if reply.decode() == 'ok':  # sanity check with length of sent object
                logging.info("Server replied OK")
                # status of sent reservations need to be set to "processed"
                for reservation in pending_reservations:
                    reservation.set_to_processed()
                break
            else:
                logging.error("Malformed reply from server: %s", reply)

        # After MAX_NUMBER_OF_RETRIES of resend tries, break to renew information (current is outdated)
        if retries > MAX_NUMBER_OF_RETRIES:
            logging.warning("Maximum retries reached, fetch new data to send.")
            # Socket is confused. Close and remove it.
            client.setsockopt(zmq.LINGER, 0)
            client.close()
            logging.info("Reconnecting to server…")
            # Create new connection
            client = context.socket(zmq.REQ)
            client.connect(server_url)
            break
        logging.warning("No response from server")
        # Socket is confused. Close and remove it.
        client.setsockopt(zmq.LINGER, 0)
        client.close()
        logging.info("Reconnecting to server…")
        # Create new connection
        client = context.socket(zmq.REQ)
        client.connect(server_url)
        logging.info("Resending (%s)", encoded_message)
        client.send(encoded_message)
        retries += 1

