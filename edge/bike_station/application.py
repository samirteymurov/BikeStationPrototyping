import logging
import random
from time import sleep

from edge.bike_station.bike_spot import BikeSpot
from edge.bike_station.sensors import SolarPanelSensor
from edge.bike_station import models
from edge.constants import ELECTRICITY_CONTRACT_KWH_PRICE
from edge.models import Constant, Reservation, ReservationStatus


class BikeStation:
    """The complete bike station with all sensors."""

    feed_in = None
    self_consumption = None
    electricity_contract_price = 0.4
    current_market_price = 0.4

    def __init__(self, number_of_spots=5):
        self.number_of_spots = number_of_spots
        self.spots = dict((i, BikeSpot(i)) for i in range(0, number_of_spots))
        # solar panel's production capacity is abstracted to equal exactly the demand
        # of the fully occupied station, i.e. number_of_spots
        self.solar_panel_sensor = SolarPanelSensor(production_capacity=number_of_spots)
        self.decide_electricity_usage()

    def get_number_of_occupied_spots(self):
        return sum(spot.occupied_sensor.occupied for spot in self.spots.values())

    def decide_electricity_usage(self):
        """Set electricity usage attributes.
        Based upon own current consumption state and market price compared to contract price,
        decide whether to feed in and/or self-consume produced electricity.
        """
        # electricity demand is abstracted to equal the number of occupied spots
        self.current_market_price = models.Constant.get_real_value_by_name('current_market_price')
        current_demand = self.get_number_of_occupied_spots()
        current_production = self.solar_panel_sensor.current_production
        if (
            current_demand == 0
            or self.electricity_contract_price < self.current_market_price
        ):
            # Exclusive feed in
            # No occupied spots means no electricity usage so feed in if producing anything
            # A higher market price means profit when feeding in all production instead of self-consuming
            self.feed_in = current_production
            self.self_consumption = 0
        else:
            if current_production <= current_demand:
                # Exclusive self-consumption
                # Producing less than or equal to own demand, so do only self-consumption
                self.feed_in = 0
                self.self_consumption = current_production
            else:
                # Producing more than own demand, so feed in the remaining electricity to grid
                self.feed_in = current_production - current_demand
                self.self_consumption = current_demand

    def calculate_feed_in_revenue(self):
        return round(self.feed_in * self.current_market_price, 4)

    def calculate_self_consumption_savings(self):
        return round(self.self_consumption * self.electricity_contract_price, 4)

    def reserve_spot(self, spot_id, reservation_id, duration):
        spot_to_reserve = self.spots.get(spot_id)
        if (
            spot_to_reserve is not None
            and spot_to_reserve.occupied_sensor.occupied
            and not spot_to_reserve.reservation_state.is_reserved

        ):
            # spot can be reserved
            created_at = spot_to_reserve.reserve(reservation_id, duration)
            print(
                f"Reservation made for spot {spot_id} at {created_at} with reservation id {reservation_id} for {duration} seconds."
            )
            return ReservationStatus.reservation_confirmed, created_at
        elif not spot_to_reserve.occupied_sensor.occupied:
            logging.warning(
                f"Cannot make reservation for spot {spot_id} (reservation {reservation_id})."
                f" Spot is not occupied anymore."
                )
            # %a, %d %b %Y %H:%M:%S UTC'
            return ReservationStatus.reservation_unfeasible, None
        else:
            logging.warning(
                f"Cannot make reservation for spot {spot_id} (reservation {reservation_id})."
                f" Is already reserved."
            )
            return ReservationStatus.reservation_unfeasible, None

    def perform_reservations(self):
        """Make reservations and update changes in DB to enable confirmation message for cloud component"""
        open_reservations = Reservation.get_open_reservation_requests()
        for reservation in open_reservations:
            # check if validity of request has expired already
            if reservation.reservation_expired():
                print("Reservation request has expired. Will be rejected.")
                reservation.update_to_unfeasible()
                continue
            # try to make reservation
            reservation_status, reservation_created_at = self.reserve_spot(
                spot_id=reservation.spot_id,
                reservation_id=reservation.reservation_id,
                duration=reservation.duration_in_seconds
            )
            if reservation_status == ReservationStatus.reservation_confirmed:
                print(f"Confirming Reservation {reservation.reservation_id}")
                reservation.update_to_confirmed(reservation_created_at)
            else:
                print(f"Rejecting Reservation {reservation.reservation_id}")
                reservation.update_to_unfeasible()

    def update_electricity_status(self):
        self.solar_panel_sensor.update_current_production()
        self.decide_electricity_usage()
        return {
            "production": self.solar_panel_sensor.current_production,
            "self_consumption": self.self_consumption,
            "consumption_saving": self.calculate_self_consumption_savings(),
            "feed_in": self.feed_in,
            "feed_in_revenue": self.calculate_feed_in_revenue(),
        }

    def run_station(self):
        spot_states = dict(
            (spot_id, spot.get_spot_state()) for spot_id, spot in self.spots.items()
        )
        electricity_status = self.update_electricity_status()
        models.ElectricityData(**electricity_status).add()
        print("\n-------------------------- Current Electricity info -----------------------------------------------------------")
        print(
            "{:<12} | {:<10} | {:<16} | {:<18} | {:<14} | {:<16}".format(
                "Market Price",
                "Production",
                "Self-consumption",
                "Consumption saving",
                "Feed-in",
                "Feed-In Revenue",
            )
        )
        print(
            "{:<12} | {:<10} | {:<16} | {:<18} | {:<14} | {:<16} \n".format(
                self.current_market_price,
                electricity_status["production"],
                electricity_status["self_consumption"],
                electricity_status["consumption_saving"],
                electricity_status["feed_in"],
                electricity_status["feed_in_revenue"],
            )
        )
        print("\n---------------------------------------- Station info --------------------------------------------------------")
        print(
            "{:<12} | {:<8} | {:<18} | {:<8} | {:<22} | {:<26} ".format(
                "Spot ID",
                "Occupied",
                "Bike Battery Level",
                "Reserved",
                "Current Reservation ID",
                "Remaining Reservation Time",
            )
        )
        for spot_id, spot_state in spot_states.items():
            battery_level = spot_state.get("bike_battery_level")
            models.SpotSensorData(spot_id=spot_id, is_occupied=spot_state["occupied"],
                                  battery_level=battery_level).add()
            print(
                "{:<12} | {:<8} | {:<18} | {:<8} | {:<22} | {:<26} ".format(
                    spot_id,
                    spot_state["occupied"],
                    "" if not battery_level else str(round(battery_level * 100, 2)),
                    spot_state["reserved"],
                    spot_state.get("reservation_id") or "",
                    spot_state.get("remaining_reservation_time") or "",
                )
            )


if __name__ == "__main__":
    print("Starting Bike Station Edge Device")
    # Set market price constant to electricity contract price until cloud component provides actual market price
    Constant(name='current_market_price', real_value=ELECTRICITY_CONTRACT_KWH_PRICE).save_or_update()
    # Setup station
    station = BikeStation()
    # If starting up happens after crash, there can be non-expired reservations that need to be added to state
    confirmed_reservations = Reservation.get_confirmed_reservations()
    for reservation in confirmed_reservations:
        if not reservation.reservation_expired():
            station.spots[reservation.spot_id].reservation_state.recover_from_db(reservation)

    while True:
        print(
            "\n \n------------------------------------------ GETTING NEW STATION STATE --------------------------------------"
        )
        station.run_station()
        print(
            "\n \n------------------------------------------ GETTING RESERVATIONS --------------------------------------------"
        )
        station.perform_reservations()

        sleep(4)
