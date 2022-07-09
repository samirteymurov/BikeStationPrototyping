import datetime

import pytz as pytz

from edge.bike_station.sensors import SpotOccupiedSensor, BikeBatterySensor


class BikeSpot:
    """Virtual sensor for one bike spot."""

    def __init__(self, spot_id):
        self.spot_id = spot_id
        self.occupied_sensor = SpotOccupiedSensor()
        self.bike_battery_sensor = BikeBatterySensor() if self.occupied_sensor.occupied else None
        self.reservation_state = ReservationState()

    def get_spot_state(self):
        """Updates current spot's state and returns sensor readings and reservation state for current state as dict."""
        self._update_spot_state()
        spot_state_info = {
            "occupied": self.occupied_sensor.occupied,
            "bike_battery_level": self._sense_bike_battery_level(),
        }
        spot_state_info.update(self._get_reservation_state())
        return spot_state_info

    def reserve(self, reservation_id, duration):
        """Create reservation for spot."""
        if self.occupied_sensor.occupied and not self.reservation_state.is_reserved:
            self.reservation_state.make_reservation(reservation_id, duration)

    def _update_spot_state(self):
        """Simulates bike is staying/getting removed/just being parked at empty spot
        Updates occupied state and reservation state.
        """
        # update occupied state:
        # Handle cases that battery sensor has to be added or removed
        old_occupied_state = self.occupied_sensor.occupied
        self.occupied_sensor.update_occupied_state()
        if old_occupied_state and not self.occupied_sensor.occupied:
            # case bike has been removed
            self.bike_battery_sensor = None
            self.reservation_state.end_reservation_if_exists()
        if not old_occupied_state and self.occupied_sensor.occupied:
            # case spot was empty and is now taken by new bike
            self.bike_battery_sensor = BikeBatterySensor()
        # update reservation state
        self.reservation_state.end_reservation_if_expired()

    def _sense_bike_battery_level(self):
        """Returns current battery level of parked bike if spot is occupied."""
        if self.bike_battery_sensor is not None:
            return self.bike_battery_sensor.sense_battery_level()

    def _get_reservation_state(self):
        reservation_state_dict = dict(
            reserved=self.reservation_state.is_reserved,
            last_reservation_state=self.reservation_state.last_reservation_id,
        )
        if self.reservation_state.is_reserved:
            reservation_state_dict[
                "remaining_reservation_time"
            ] = self.reservation_state.remaining_time
            reservation_state_dict[
                "reservation_id"
            ] = self.reservation_state.reservation_id

        return reservation_state_dict


class ReservationState:
    def __init__(self):
        # dummy reservation creation timestamp
        self.default_created_at = datetime.datetime(
            2000, 1, 1, 0, 0, 0, tzinfo=pytz.utc
        )
        self.reservation_created_at = self.default_created_at
        self.reservation_id = 0
        self.last_reservation_id = None  # only for monitoring/testing purposes
        self.duration = 0

    @property
    def is_reserved(self):
        # valid reservation if reservation_created_at is not dummy value
        return self.reservation_created_at != self.default_created_at

    @property
    def remaining_time(self):
        if not self.is_reserved:
            return 0
        return (
            self.duration
            - (datetime.datetime.utcnow() - self.reservation_created_at).total_seconds()
        )

    def make_reservation(self, reservation_id, duration):
        self.reservation_created_at = datetime.datetime.utcnow()
        self.reservation_id = reservation_id
        self.duration = duration

    def end_reservation_if_exists(self):
        if self.is_reserved:
            self.reservation_created_at = self.default_created_at
            self.last_reservation_id = self.reservation_id
            self.reservation_id = 0
            self.duration = 0

    def end_reservation_if_expired(self):
        if self.remaining_time <= 0:
            self.end_reservation_if_exists()
