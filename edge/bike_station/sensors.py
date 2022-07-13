import datetime
import random


class SpotOccupiedSensor:
    def __init__(self):
        self.occupied = bool(random.getrandbits(1))

    def update_occupied_state(self):
        """Generates new occupied state on the parking spot based on current state.
        If occupied, it is more likely it stays occupied.
        """
        if self.occupied:
            # If spot is occupied, with 85% probability it is stays occupied.
            self.occupied = random.random() <= 0.85
        else:
            # If spot is not occupied, getting occupied is a 50-50 chance
            self.occupied = bool(random.getrandbits(1))


class BikeBatterySensor:
    def __init__(self):
        # initial is battery level never 0% or 100%
        self.battery_level = round(random.uniform(0.01, 0.99), 4)
        self.level_increase_per_second = 0.0033
        self.last_sensed = datetime.datetime.utcnow()

    def _update_battery_level(self):
        """Increases battery level depending on seconds passed since last reading.
        No effect on battery level, if battery is fully charged
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


class SolarPanelSensor:
    """Sensor for production of solar panel."""

    def __init__(self, production_capacity):
        self.capacity = production_capacity
        self.current_production = random.randint(0, self.capacity)

    def update_current_production(self):
        """Update current production with new random value."""
        self.current_production = random.randint(0, self.capacity)
