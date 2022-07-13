import datetime
import enum
import os
import json

import pytz
from sqlalchemy import Column, Integer, DateTime, Boolean, Enum, REAL, String, false, true
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from edge.constants import ELECTRICITY_CONTRACT_KWH_PRICE

load_dotenv()

engine = create_engine(f'sqlite:///sqlite.db', echo=False)  # sqlite db relative path
Session = sessionmaker(bind=engine)
# create a Session
session = Session()

Base = declarative_base()


class Status(enum.Enum):
    created = 0
    processed = 1
    failed = 2
    waiting = 3


class Constant(Base):
    __tablename__ = "constant"
    name = Column(String, primary_key=True)
    real_value = Column(REAL, default=ELECTRICITY_CONTRACT_KWH_PRICE)

    def save_or_update(self):
        session.merge(self)
        session.commit()
        return self

    @staticmethod
    def get_real_value_by_name(name):
        return session.query(Constant).filter(Constant.name == name).first().real_value


class SpotSensorData(Base):
    __tablename__ = "spot_sensor_reading"
    read_id = Column(Integer, primary_key=True)
    read_timestamp = Column(DateTime(timezone=True), server_default=func.now(tz=pytz.utc))
    update_timestamp = Column(DateTime(timezone=True), onupdate=func.now(tz=pytz.utc))
    spot_id = Column(Integer, nullable=False)
    is_occupied = Column(Boolean, default=False)
    battery_level = Column(REAL)
    sent_status = Column(Enum(Status), default=Status.created)

    def add(self):
        session.add(self)
        session.commit()
        return self

    @staticmethod
    def clean_processed():
        session.query(SpotSensorData).filter(
            SpotSensorData.sent_status == Status.processed
        ).delete()
        session.commit()

    @staticmethod
    def get_oldest_n_readings(n):
        return session.query(SpotSensorData).filter(
            SpotSensorData.sent_status == Status.created
        ).limit(n).all()

    @staticmethod
    def set_to_processed(last_read_id):
        session.query(SpotSensorData).filter(
            SpotSensorData.read_id <= last_read_id
        ).update({"sent_status": Status.processed})
        session.commit()

    @staticmethod
    def make_query_dictionary(query):
        summary_dict = {'0': [], '1': [], '2': [], '3': [], '4': []}
        for reading in query:
            spot_id = reading.spot_id
            summary_dict[str(spot_id)].append(
                {
                    'datetime': reading.read_timestamp,
                    'reading_id': reading.read_id,
                    'is_occupied': reading.is_occupied,
                    'battery_level': reading.battery_level,
                }
            )
        return summary_dict


class ElectricityData(Base):
    __tablename__ = "electricity_data"
    data_item_id = Column(Integer, primary_key=True)
    data_timestamp = Column(DateTime(timezone=True), server_default=func.now(tz=pytz.utc))
    production = Column(Integer, nullable=False, default=0)
    self_consumption = Column(Integer, nullable=False, default=0)
    feed_in = Column(Integer, nullable=False, default=0)
    consumption_saving = Column(REAL, nullable=False, default=0)
    feed_in_revenue = Column(REAL, nullable=False, default=0)
    sent_status = Column(Enum(Status), default=Status.created)

    def add(self):
        session.add(self)
        session.commit()
        return self

    @staticmethod
    def clean_processed():
        session.query(ElectricityData).filter(
            ElectricityData.sent_status == Status.processed
        ).delete()
        session.commit()

    @staticmethod
    def get_oldest_n_readings(n):
        return session.query(ElectricityData).filter(
            ElectricityData.sent_status == Status.created
        ).limit(n).all()

    @staticmethod
    def set_to_processed(last_sent_item_id):
        session.query(ElectricityData).filter(
            ElectricityData.data_item_id <= last_sent_item_id
        ).update({"sent_status": Status.processed})
        session.commit()

    @staticmethod
    def make_query_dictionary(query):
        data_dict = {}
        for data_item in query:
            item_id = data_item.data_item_id
            data_dict[str(item_id)] = {
                    "datetime": data_item.data_timestamp,
                    "production": data_item.production,
                    "self_consumption": data_item.self_consumption,
                    "consumption_saving": data_item.consumption_saving,
                    "feed_in": data_item.feed_in,
                    "feed_in_revenue": data_item.feed_in_revenue,
                }

        return data_dict


class ReservationStatus(enum.Enum):
    reservation_requested = 0
    reservation_confirmed = 1
    reservation_unfeasible = 2


class Reservation(Base):
    __tablename__ = "reservations"
    reservation_id = Column(Integer, primary_key=True)
    received_timestamp = Column(DateTime(timezone=True), server_default=func.now(tz=pytz.utc))
    confirmed_at = Column(DateTime(timezone=True))
    spot_id = Column(Integer, nullable=False)
    duration_in_seconds = Column(Integer, nullable=False)
    status = Column(Enum(ReservationStatus), default=ReservationStatus.reservation_requested)
    response_sent = Column(Boolean, default=False, nullable=False)

    def add(self):
        session.add(self)
        session.commit()
        return self

    def reservation_expired(self):
        # Request expires if after receiving the request the full duration time has already passed
        if self.status == ReservationStatus.reservation_requested:
            return int(
                self.duration_in_seconds
                - (datetime.datetime.utcnow() - self.received_timestamp).total_seconds()
            ) <= 0
        # Confirmed requests expire when full duration time has passed after confirmation
        if self.status == ReservationStatus.reservation_confirmed:
            return int(
                self.duration_in_seconds
                - (datetime.datetime.utcnow() - self.confirmed_at).total_seconds()
            ) <= 0
        return False

    def update_to_confirmed(self, confirmation_timestamp):
        self.status = ReservationStatus.reservation_confirmed
        self.confirmed_at = confirmation_timestamp
        session.commit()

    def update_to_unfeasible(self):
        self.status = ReservationStatus.reservation_unfeasible
        session.commit()

    def update_response_sent(self):
        self.response_sent = True
        session.commit()

    @staticmethod
    def clean_finished():
        # delete all rejected reservations which have been communicated already
        session.query(Reservation).filter(
            Reservation.status == ReservationStatus.reservation_unfeasible,
            Reservation.response_sent == true()
        ).delete()
        # get confirmed and communicated reservations and clean if expired
        for reservation in session.query(Reservation).filter(
            Reservation.status == ReservationStatus.reservation_confirmed,
            Reservation.response_sent == true()
        ).all():
            if reservation.reservation_expired():
                session.delete(reservation)
        session.commit()

    @staticmethod
    def get_open_reservation_requests():
        return session.query(Reservation).filter(Reservation.status == ReservationStatus.reservation_requested).all()

    @staticmethod
    def get_reservation_by_id(reservation_id):
        return session.query(Reservation).get(reservation_id)

    @staticmethod
    def get_confirmed_reservations():
        """Get confirmed and communicated reservations
        Note: to be used to get reservation state after crash of application
        """
        return session.query(Reservation).filter(
            Reservation.status == ReservationStatus.reservation_confirmed,
            Reservation.response_sent == true()
        ).all()

    @staticmethod
    def get_confirmed_reservation_requests():
        """Gets processed and confirmed reservation requests that haven't been communicated back."""
        return session.query(Reservation).filter(
            Reservation.status == ReservationStatus.reservation_confirmed,
            Reservation.response_sent == false()
        ).all()

    @staticmethod
    def make_confirmed_reservations_dict(query):
        confirmed_reservations_dict = {}
        for reservation in query:
            confirmed_reservations_dict[str(reservation.reservation_id)] = reservation.confirmed_at
        return confirmed_reservations_dict

    @staticmethod
    def get_rejected_reservation_requests():
        """Gets processed but unfeasible reservation requests that haven't been communicated back.
        """
        return session.query(Reservation).filter(
            Reservation.status == ReservationStatus.reservation_unfeasible,
            Reservation.response_sent == false()
        ).all()


Base.metadata.create_all(engine)

