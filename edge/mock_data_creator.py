import time, random
from models import SpotSensorData, Status

while True:
    spot_id = random.randint(0, 5)
    is_occupied = bool(random.getrandbits(1))
    sensor_read = SpotSensorData(spot_id=spot_id, is_occupied=is_occupied).add()
    time.sleep(5)
