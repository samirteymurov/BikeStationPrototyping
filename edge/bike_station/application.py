from time import sleep

from edge.bike_station.sensors import BikeSpotSensor


def run_station(numer_of_spots):
    # create bike spot sensors
    spot_sensors = [BikeSpotSensor(spot_id=i) for i in range(0, numer_of_spots)]
    while True:
        print("Getting new sensor readings...")
        new_sensor_readings = [sensor.get_spot_sensor_readings() for sensor in spot_sensors]
        for sensor_reading in new_sensor_readings:
            if sensor_reading["occupied"]:
                occupied_state_txt = "occupied"
                battery_level_txt = ", battery level at {percentage}%".format(
                    percentage=str(round(sensor_reading["bike_battery_level"] * 100, 2))
                )
            else:
                occupied_state_txt = "free"
                battery_level_txt = ""
            print(
                f"Spot {sensor_reading['spot_id']} is {occupied_state_txt}{battery_level_txt}."
            )
        sleep(5)


if __name__ == '__main__':
    print("Starting...")
    run_station(5)