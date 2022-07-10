import datetime
import enum
import os

import pytz
from sqlalchemy import Column, Integer, DateTime, Boolean, Enum, REAL, func, create_engine, true
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
    sensor_reading_timestamp = Column(DateTime(timezone=True), primary_key=True)
    sensor_reading_id = Column(Integer, nullable=False)
    spot_id = Column(Integer, nullable=False, primary_key=True)
    is_occupied = Column(Boolean, default=False)
    battery_level = Column(REAL)

    def add(self):
        session.add(self)
        session.commit()
        return self

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

    def set_to_processed(self):
        self.sent_status = MessageStatus.processed
        session.commit()

    @staticmethod
    def get_pending_reservations():
        """Get pending reservations, ordered by descending creation
        """
        return (
            session.query(ReservationRequest)
            .filter(ReservationRequest.sent_status == MessageStatus.created)
            .order_by("creation_timestamp")
            .all()
        )

    @staticmethod
    def make_query_dictionary(query):
        reservations_dict = {}
        for reservation in query:
            reservation_id = reservation.reservation_id
            reservations_dict[str(reservation_id)] = {
                'created_at': reservation.creation_timestamp,
                'spot_id': reservation.spot_id,
                'duration': reservation.duration_in_seconds,
            }
        return reservations_dict

    @staticmethod
    def clean_processed():
        session.query(ReservationRequest).filter(
            ReservationRequest.sent_status == MessageStatus.processed
        ).delete()
        session.commit()


class ReservationStatus(enum.Enum):
    reservation_requested = 0
    reservation_confirmed = 1
    reservation_unfeasible = 2
    no_reservation = 3


class CurrentSpotState(Base):
    """Represents most recent state of the station's spot known to the cloud component.
    """
    __tablename__ = "current_spot_state"
    spot_id = Column(Integer, primary_key=True)
    is_occupied = Column(Boolean, default=False)
    battery_level = Column(REAL)
    reservation_status = Column(Enum(ReservationStatus), default=ReservationStatus.no_reservation)
    reservation_id = Column(Integer)
    reservation_valid_from = Column(DateTime(timezone=True))
    reservation_duration = Column(Integer)

    @staticmethod
    def get_current_states():
        return session.query(CurrentSpotState).order_by("spot_id").all()

    @staticmethod
    def get_reservable_spots():
        return session.query(CurrentSpotState).filter(
            CurrentSpotState.reservation_status == ReservationStatus.no_reservation,
            CurrentSpotState.is_occupied == true()
        ).all()

    @staticmethod
    def get_all_reserved_spots():
        return session.query(CurrentSpotState).filter(
            CurrentSpotState.reservation_status == ReservationStatus.reservation_confirmed,
            CurrentSpotState.reservation_valid_from != None,
            CurrentSpotState.reservation_duration != None,
        ).all()

    def update_occupied_and_battery_state(self, is_occupied, battery_level=0.0):
        self.is_occupied = is_occupied
        self.battery_level = battery_level
        session.commit()

    def end_reservation(self):
        self.reservation_status = ReservationStatus.no_reservation
        self.reservation_id = None
        self.reservation_duration = None
        self.reservation_valid_from = None
        session.commit()

    def update_reservation_state(
            self, reservation_status: ReservationStatus,
            reservation_id=None,
            duration=None,
            valid_from=None,
    ):
        if reservation_status == ReservationStatus.no_reservation:
            self.end_reservation()
            return
        else:
            self.reservation_status = reservation_status
            self.reservation_id = reservation_id
            self.reservation_valid_from = valid_from
            if duration:
                self.reservation_duration = duration
        session.commit()

    def update_expired_reservation(self):
        if self.reservation_valid_from:
            remaining_time = (
                    self.reservation_duration -
                    (datetime.datetime.utcnow() - self.reservation_valid_from).total_seconds()
            )
            # remove reservation if it is expired
            if remaining_time <= 0:
                self.end_reservation()

    @staticmethod
    def update_all_expired_reservations():
        for spot_state in CurrentSpotState.get_all_reserved_spots():
            spot_state.update_expired_reservation()

    def make_inital_entry(self):
        """Use only if no entry for the spot exists yet."""
        session.add(self)
        session.commit()
        return self


Base.metadata.create_all(engine)
