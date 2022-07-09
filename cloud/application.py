import enum
import logging
import random
from time import sleep

from cloud.client.reservation_maker import ReservationMaker
from cloud.constants import NUMBER_OF_SPOTS
from cloud.models import CurrentSpotState


def initialize_spot_states_if_none():
    current_states = CurrentSpotState.get_current_states()
    if not current_states:
        for spot_id in range(1, NUMBER_OF_SPOTS):
            print("spot_id: "+ str(spot_id))
            spot = CurrentSpotState(spot_id=spot_id).make_inital_entry()


if __name__ == "__main__":
    initialize_spot_states_if_none()
    while True:
        # TODO:
        #  logging.info spot states
        #  logging.info electricity consumption state
        print("----------------------------------- Making Reservation -----------------------------")
        # make random decision whether to reserve a spot
        reserve_spot = bool(random.getrandbits(1))
        if reserve_spot:
            reservable_spots = CurrentSpotState.get_reservable_spots()
            # randomly choose one of the reservable spots and a duration time
            spot = reservable_spots[random.randint(0, len(reservable_spots)-1)]
            duration = random.randint(60, 120)  # Should be (5 min, 15 min) in reality but (60, 120) is better for demo
            ReservationMaker.make_reservation(spot, duration=duration)

        sleep(5)

