from random import randint
import os
import itertools
import logging
import time
import zmq
import json
from dotenv import load_dotenv
load_dotenv()
from models import Constant

logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)
context = zmq.Context()
server = context.socket(zmq.REP)
print(os.getenv('bind_address'))
server.bind(os.getenv("bind_address"))
for cycles in itertools.count():
    request = server.recv()
    current_market_price = json.loads(request.decode())
    # write it to constants table so that application can read it
    Constant(name='current_market_price', real_value=current_market_price).add()
    print(request)
    logging.info("Normal request (%s)", request)
    # time.sleep(1)
    # after making sure that all data have been processed send ok reply
    server.send('ok'.encode())
