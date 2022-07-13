# script for calling every hour as cronjob
import os, sys
from models import SpotSensorData, ElectricityData, Reservation
sys.path.insert(1, os.path.join(sys.path[0], '..'))  # to avoid possible relative import errors
SpotSensorData.clean_processed()
ElectricityData.clean_processed()
Reservation.clean_finished()
