import datetime
import random


class BikeSpotSensor:
    """Virtual sensor for one bike spot.
    """

    def __init__(self, spot_id):
        self.spot_id = spot_id
        self.occupied = bool(random.getrandbits(1))
        self.bike_battery_sensor = BikeBatterySensor() if self.occupied else None

    def get_spot_sensor_readings(self):
        """Updates current spot's state and returns sensor readings for current state in dict."""
        self._update_spot_state()
        return {
            "spot_id": self.spot_id,
            "occupied": self.occupied,
            "bike_battery_level": self._sense_bike_battery_level()
        }

    def _update_spot_state(self):
        """Simulate bike is staying/getting removed/just being parked at empty spot"""
        new_occupied_state = self._generate_new_occupied_state()
        if self.occupied and not new_occupied_state:
            # case bike has been removed
            self.bike_battery_sensor = None
        if not self.occupied and new_occupied_state:
            # case spot was empty and is now taken by new bike
            self.bike_battery_sensor = BikeBatterySensor()
        # nothing to change in battery sensor for remaining cases
        self.occupied = new_occupied_state

    def _generate_new_occupied_state(self):
        """Generates new occupied state on the parking spot based on current state.
        If occupied, it is more likely it stays occupied.
        """
        if self.occupied:
            # If spot is occupied, with 65% probability it is stays occupied.
            return random.random() <= 0.65
        else:
            # If spot is not occupied, getting occupied is a 50-50 chance
            return bool(random.getrandbits(1))

    def _sense_bike_battery_level(self):
        """Returns current battery level of parked bike if spot is occupied."""
        if self.bike_battery_sensor:
            return self.bike_battery_sensor.sense_battery_level()


class BikeBatterySensor:
    def __init__(self):
        # initial is battery level never 0% or 100%
        self.battery_level = round(random.uniform(0.01, 0.99), 4)
        self.level_increase_per_second = 0.0033
        self.last_sensed = datetime.datetime.utcnow()

    def _update_battery_level(self):
        """Increases battery level depending on seconds passed since last reading.
        No effect on battery level, if battery is fully charged
        Returns:
            updated battery level
        """
        now = datetime.datetime.utcnow()
        seconds_passed = (now - self.last_sensed).total_seconds()
        self.last_sensed = now
        if self.battery_level == 1:
            return
        level_increase = round(seconds_passed * self.level_increase_per_second, 4)
        increased_level = self.battery_level + level_increase
        # battery doesn't go over 100%
        self.battery_level = increased_level if increased_level <= 1 else 1

    def sense_battery_level(self):
        self._update_battery_level()
        return self.battery_level
