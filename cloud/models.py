import enum
import os

import pytz
from sqlalchemy import Column, Integer, DateTime, Boolean, Enum, REAL, func, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
load_dotenv()

engine = create_engine(f'sqlite:////{os.getenv("sqlite_absolute_path")}', echo=False)
Session = sessionmaker(bind=engine)
# create a Session
session = Session()

Base = declarative_base()


class SpotStateData(Base):
    """This table is meant to store all received data on a spot.
    Can be used for data analysis e.g. to improve business model, functionality, etc.
    """
    __tablename__ = "spot_state"
    update_timestamp = Column(DateTime(timezone=True), primary_key=True)
    spot_id = Column(Integer, nullable=False, primary_key=True)
    is_occupied = Column(Boolean, default=False)
    battery_level = Column(REAL)
    reserved = Column(Boolean, default=False)


class MessageStatus(enum.Enum):
    created = 0
    processed = 1
    failed = 2
    waiting = 3


class ReservationRequest(Base):
    __tablename__ = "reservation_request"
    reservation_id = Column(Integer, primary_key=True)
    creation_timestamp = Column(DateTime(timezone=True), server_default=func.now(tz=pytz.utc))
    spot_id = Column(Integer, nullable=False)
    duration_in_seconds = Column(Integer, nullable=False)
    sent_status = Column(Enum(MessageStatus), default=MessageStatus.created)

    def add(self):
        session.add(self)
        session.commit()
        return self

    @staticmethod
    def get_pending_reservations():
        """Get pending reservations, ordered by descending creation
        """
        return (
            ReservationRequest.session.query(ReservationRequest)
            .filter(ReservationRequest.sent_status == MessageStatus.created)
            .limit().all().order_by("creation_timestamp")
        )

    @staticmethod
    def make_query_dictionary(query):
        reservations_dict = {}
        for reservation in query:
            reservation_id = reservation.reservation_id
            reservations_dict[str(reservation_id)] = {
                'created_at': reservation.invoked_timestamp,
                'spot_id': reservation.spot_id,
                'duration': reservation.duration_in_seconds,
            }
        return reservations_dict

    # def clear_expired_reservations

    @staticmethod
    def set_to_processed(reservation_id):
        session.query(ReservationRequest).get(reservation_id).update({"sent_status": MessageStatus.processed})
        session.commit()
    # def clear_sent_reservations

    @staticmethod
    def clean_processed():
        session.query(ReservationRequest).filter(ReservationRequest.sent_status==MessageStatus.processed).delete()
        session.commit()


class ReservationStatus(enum.Enum):
    reservation_requested = 0
    reservation_confirmed = 1
    no_reservation = 2


class CurrentSpotState(Base):
    """Represents most recent state of the station's spot known to the cloud component.
    """
    __tablename__ = "current_spot_state"
    spot_id = Column(Integer, primary_key=True)
    is_occupied = Column(Boolean, default=False)
    battery_level = Column(REAL, default=0.0)
    reservation_status = Column(Enum(ReservationStatus), default=ReservationStatus.no_reservation)
    reservation_id = Column(Integer)

    @staticmethod
    def get_current_states():
        return session.query(CurrentSpotState).order_by("spot_id").all()


    @staticmethod
    def get_reservable_spots():
        return session.query(CurrentSpotState).filter(
            CurrentSpotState.reservation_status == ReservationStatus.no_reservation
            and not CurrentSpotState.is_occupied
        ).all()

    def update_occupied_state(self, is_occupied):
        self.is_occupied = is_occupied
        session.commit()

    def update_reservation_state(self, reservation_status: ReservationStatus):
        self.reservation_status = reservation_status
        session.commit()

    def make_inital_entry(self):
        """Use only if no entry for the spot exists yet."""
        session.add(self)
        session.commit()
        return self


Base.metadata.create_all(engine)
