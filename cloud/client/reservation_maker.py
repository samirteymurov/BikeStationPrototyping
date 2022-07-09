import logging

from cloud.models import CurrentSpotState, ReservationRequest, ReservationStatus


class ReservationMaker:
    @staticmethod
    def make_reservation(
            spot: CurrentSpotState,
            duration: int
    ):
        ReservationRequest(spot_id=spot.spot_id, duration_in_seconds=duration).add()
        spot.update_reservation_state(ReservationStatus.reservation_requested)
        logging.info(
            f"Request created for reservation if spot {spot.spot_id}, reservation duration: {duration}"
        )
