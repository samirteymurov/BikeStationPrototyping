from random import randint
import os
import itertools
import logging
import zmq
import json
from dotenv import load_dotenv

from edge.constants import ELECTRICITY_CONTRACT_KWH_PRICE

load_dotenv()
from models import Constant, Reservation

logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)
context = zmq.Context()
server = context.socket(zmq.REP)
logging.info('Listening to the incoming requests...')
server.bind(os.getenv("bind_address"))
for cycles in itertools.count():
    normal_request = True
    request = server.recv()
    request_dict = json.loads(request.decode())
    current_market_price = request_dict.get("current_market_price")
    if not current_market_price:
        normal_request = False
        logging.error("Malformed request: Current market price not provided, using default value..")
        current_market_price = ELECTRICITY_CONTRACT_KWH_PRICE
    else:
        logging.info(f"Received current market price: {current_market_price}")
    # write it to constants table so that application can read it
    Constant(name='current_market_price', real_value=current_market_price).save_or_update()

    reservations = request_dict.get("reservations")
    for reservation_id, reservation_details in reservations.items():
        spot_id = reservation_details.get("spot_id")
        duration = reservation_details.get("duration")
        logging.info(f"Received reservation {reservation_id} for spot {spot_id}, duration: {duration}")
        # create entry for open reservations that have not been received yet
        if not Reservation.get_reservation_by_id(reservation_id):
            logging.debug(f"Saving reservation {reservation_id}")
            try:
                Reservation(
                    reservation_id=reservation_id,
                    spot_id=spot_id,
                    duration_in_seconds=duration,
                ).add()
            except Exception as e:
                logging.error(
                    "Something went wrong when processing reservation info: "
                    + str(e)
                )
                normal_request = False


    if normal_request:
        logging.info("Normal request.")
    # time.sleep(1)
    # after making sure that all data have been processed send ok reply
    server.send('ok'.encode())
