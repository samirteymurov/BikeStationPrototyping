from unittest import TestCase
from unittest.mock import patch

from parameterized import parameterized

from edge.bike_station.bike_spot import BikeSpot
from edge.bike_station.sensors import BikeBatterySensor


class TestBikeSpot(TestCase):

    @parameterized.expand([
        ("occupied_to_occupied", True, 1, 0.3, True),
        ("occupied_to_free", True, 1, 0.7, False),
        ("free_to_occupied", False, 1, 0.3, True),
        ("free_to_free", False, 0, 0.7, False),

    ])
    @patch("random.random")
    @patch("random.getrandbits")
    def test_update_spot_state(
            self,
            _label,
            initial_occupied,
            random_bit,
            random_probability,
            expected_occupied,
            mock_random_bits,
            mock_random_probability
    ):
        mock_random_bits.return_value = random_bit
        # set probability such that sensor updates new occupied state as wanted
        mock_random_probability.return_value = random_probability
        bike_spot = BikeSpot(1)
        bike_spot.occupied_sensor.occupied = initial_occupied
        if initial_occupied:
            battery_sensor = BikeBatterySensor()
            battery_sensor.battery_level = 0.2
            bike_spot.bike_battery_sensor = battery_sensor
        else:
            bike_spot.bike_battery_sensor = None

        bike_spot._update_spot_state()
        self.assertEqual(expected_occupied, bike_spot.occupied_sensor.occupied)
        if not expected_occupied:
            self.assertIsNone(bike_spot.bike_battery_sensor)


