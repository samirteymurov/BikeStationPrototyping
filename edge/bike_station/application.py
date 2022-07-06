import random
from time import sleep

from edge.bike_station.bike_spot import BikeSpot
from edge.bike_station.sensors import SolarPanelSensor
from edge.bike_station import models


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
        # self.electricity_contract_price = 0.4  # not really based on real world
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

    def calculate_feed_in_profit(self, current_market_price):
        if current_market_price is None:
            return "unknown"
        return round(self.feed_in * current_market_price, 4)

    def calculate_self_consumption_savings(self):
        return round(self.self_consumption * self.electricity_contract_price, 4)

    def reserve_spot(self, spot_id, code_to_unlock, duration):
        spot_to_reserve = self.spots.get(spot_id)
        if (
            spot_to_reserve is not None
            and not spot_to_reserve.reservation_state.is_reserved
        ):
            spot_to_reserve.reserve(code_to_unlock, duration)
            print(
                f"Reservation made for spot {spot_id} with unlock code {code_to_unlock} for {duration} seconds."
            )
        else:
            print(f"Cannot make reservation for spot {spot_id}. Is already reserved.")

    def run_station(self):
        spot_states = dict(
            (spot_id, spot.get_spot_state()) for spot_id, spot in self.spots.items()
        )
        self.solar_panel_sensor.update_current_production()
        self.decide_electricity_usage()
        print("\n-------------------------- Current Electricity info --------------------------------")
        print(
            "{:<12} | {:<10} | {:<16} | {:<18} | {:<14} | {:<16}".format(
                "Market Price",
                "Production",
                "Self-consumption",
                "Consumption saving",
                "Feed-in",
                "Production Revenue",
            )
        )
        print(
            "{:<12} | {:<10} | {:<16} | {:<18} | {:<14} | {:<16} \n".format(
                self.current_market_price,
                self.solar_panel_sensor.current_production,
                self.self_consumption,
                self.calculate_self_consumption_savings(),
                self.feed_in,
                self.calculate_feed_in_profit(self.current_market_price),
            )
        )
        print("\n---------------------------------------- Station info --------------------------------------")
        print(
            "{:<12} | {:<8} | {:<18} | {:<8} | {:<26} | {:<22} | {:<19}".format(
                "Spot ID",
                "Occupied",
                "Bike Battery Level",
                "Reserved",
                "Remaining Reservation Time",
                "Current Reservation ID",
                "Last Reservation ID"
            )
        )
        for spot_id, spot_state in spot_states.items():
            battery_level = spot_state.get("bike_battery_level")
            models.SpotSensorData(spot_id=spot_id, is_occupied=spot_state["occupied"],
                                  battery_level=battery_level).add()
            print(
                "{:<12} | {:<8} | {:<18} | {:<8} | {:<26} | {:<22} | {:<19}".format(
                    spot_id,
                    spot_state["occupied"],
                    "" if not battery_level else str(round(battery_level * 100, 2)),
                    # TODO do we need below fields?
                    spot_state["reserved"],
                    spot_state.get("remaining_reservation_time") or "",
                    spot_state.get("reservation_id") or "",
                    spot_state.get("last_reservation_id") or "",
                )
            )


if __name__ == "__main__":
    print("Starting...")
    station = BikeStation(5)
    while True:
        print(
            "\n \n####################################### GETTING NEW STATION STATE ##################################"
        )
        station.run_station()
        # make random reservation, should be replaced with making reservations when receiving requests
        print("\n------------------------------Making Reservation--------------------------------------")
        station.reserve_spot(
            spot_id=random.randint(0, 5),
            code_to_unlock=random.randint(1000, 9999),
            duration=random.randint(30, 120),
        )
        sleep(5)
