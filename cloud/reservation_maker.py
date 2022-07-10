import logging

from cloud.models import CurrentSpotState, ReservationRequest, ReservationStatus


class ReservationMaker:
    @staticmethod
    def make_reservation(
            spot: CurrentSpotState,
            duration: int
    ):
        reservation_request = ReservationRequest(
            spot_id=spot.spot_id,
            duration_in_seconds=duration
        ).add()
        reservation_id = reservation_request.reservation_id
        spot.update_reservation_state(
            reservation_status=ReservationStatus.reservation_requested,
            reservation_id=reservation_id,
            duration=duration,
        )
        logging.info(
            f"Request created for reservation {reservation_id} if spot {spot.spot_id}, reservation duration: {duration}"
        )
        return reservation_id
