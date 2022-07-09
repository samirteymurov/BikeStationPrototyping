import datetime
import enum
import os
import json

import pytz
from sqlalchemy import Column, Integer, DateTime, Boolean, Enum, REAL, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
load_dotenv()

engine = create_engine(f'sqlite:////{os.getenv("sqlite_absolute_path")}', echo=False)
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
    integer_value = Column(Integer)
    real_value = Column(REAL)
    string_value = Column(String)

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
        session.query(SpotSensorData).filter(SpotSensorData.sent_status==Status.processed).delete()
        session.commit()

    @staticmethod
    def get_oldest_n_readings(n):
        # TODO shouldn't this be latest instead?
        return session.query(SpotSensorData).filter(SpotSensorData.sent_status==Status.created).limit(n).all()

    @staticmethod
    def set_to_processed(last_read_id):
        session.query(SpotSensorData).filter(SpotSensorData.read_id <= last_read_id).update({"sent_status": Status.processed})
        session.commit()

    @staticmethod
    def encode_query(query):
        summary_dict = {'0': [], '1': [], '2': [], '3': [], '4': []}
        for reading in query:
            spot_id = reading.spot_id
            summary_dict[str(spot_id)].append(
                [{'datetime': reading.read_timestamp, 'is_occupied': reading.is_occupied}])
        return json.dumps(summary_dict, default=str).encode()


class ReservationStatus(enum.Enum):
    reservation_requested = 0
    reservation_confirmed = 1
    reservation_unfeasible = 2


class Reservation(Base):
    __tablename__ = "reservations"
    reservation_id = Column(Integer, primary_key=True)
    received_timestamp = Column(DateTime(timezone=True), server_default=func.now(tz=pytz.utc))
    created_timestamp = Column(DateTime(timezone=True))
    spot_id = Column(Integer, nullable=False)
    duration_in_seconds = Column(Integer, nullable=False)
    status = Column(Enum(ReservationStatus), default=ReservationStatus.reservation_requested)

    def add(self):
        session.add(self)
        session.commit()
        return self

    def set_to_confirmed(self, created_timestamp):
        self.status = ReservationStatus.reservation_confirmed
        self.created_timestamp = created_timestamp
        session.commit()

    def set_to_unfeasible(self):
        self.status = ReservationStatus.reservation_unfeasible
        session.commit()

    @staticmethod
    def clean_finished():
        session.query(Reservation).filter(Reservation.response_sent).delete()
        session.commit()

    @staticmethod
    def get_open_reservation_requests():
        return session.query(Reservation).filter(Reservation.status == ReservationStatus.reservation_requested).all()

    @staticmethod
    def clean_when_bike_removed(spot_id):
        session.query(Reservation).filter(
            Reservation.spot_id == spot_id and Reservation.status == ReservationStatus.reservation_confirmed
        ).delete()
        session.commit()


Base.metadata.create_all(engine)

