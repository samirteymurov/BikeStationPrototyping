import datetime
import random
from time import sleep

from cloud.reservation_maker import ReservationMaker
from cloud.constants import NUMBER_OF_SPOTS
from cloud.models import CurrentSpotState, ReservationStatus


def initialize_spot_states_if_none():
    current_states = CurrentSpotState.get_current_states()
    if not current_states:
        for spot_id in range(0, NUMBER_OF_SPOTS):
            CurrentSpotState(spot_id=spot_id).make_inital_entry()


def display_station_state():
    # update expired reservations before displaying
    CurrentSpotState.update_all_expired_reservations()
    print("\n \n---------------------------------------- Station State ---------------------------------------------------------------")
    print(
        "{:<12} | {:<8} | {:<18} | {:<21} |  {:<14} | {:<9}".format(
            "Spot ID",
            "Occupied",
            "Bike Battery Level",
            "Reservation Status",
            "Reservation ID",
            "Remaining",
        )
    )
    for spot_state in CurrentSpotState.get_current_states():
        remaining_time = None
        if spot_state.reservation_valid_from is not None and spot_state.reservation_duration is not None:
            remaining_time = int(
                        spot_state.reservation_duration -
                        (datetime.datetime.utcnow() - spot_state.reservation_valid_from).total_seconds()
                )
        print(
            "{:<12} | {:<8} | {:<18} | {:<21} | {:<14} | {:<9}".format(
                str(spot_state.spot_id),
                str(spot_state.is_occupied),
                "" if not spot_state.battery_level else str(round(spot_state.battery_level * 100, 2)),
                spot_state.reservation_status.name,
                str(spot_state.reservation_id or ""),
                remaining_time or "",
            )
        )


if __name__ == "__main__":
    initialize_spot_states_if_none()
    while True:
        # TODO: display  electricity consumption state
        # Display current station state known to cloud component
        display_station_state()
        reservable_spots = CurrentSpotState.get_reservable_spots()
        if not reservable_spots:
            print("No spots to reserve..")
            sleep(5)
            continue

        # make decision whether to reserve a spot or not with 33% likelihood of making reservation
        reserve_spot = random.random() <= 0.33
        if reserve_spot:
            print("\n----------------------------------- Creating Reservation ---------------------------------------------------------")

            # randomly choose one of the reservable spots and a duration time
            spot = reservable_spots[random.randint(0, len(reservable_spots)-1)]
            duration = random.randint(20, 50)  # Should be (5 min, 15 min) in reality but (20, 50) is better for demo
            reservation_id = ReservationMaker.make_reservation(spot, duration=duration)
            print(
                "{:<12} | {:<14} | {:<20} \n {:<12} | {:<14} | {:<20}".format(
                    "Spot ID",
                    "Reservation ID",
                    "Reservation Duration",
                    spot.spot_id,
                    reservation_id,
                    duration,
                )
            )
        sleep(2)

