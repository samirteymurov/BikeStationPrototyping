import enum
from sqlalchemy import Column, Integer, DateTime, Boolean, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


engine = create_engine("sqlite:///sqlite.db", echo=True)
Session = sessionmaker(bind=engine)
# create a Session
session = Session()

Base = declarative_base()


class Status(enum.Enum):
    created = 0
    sent = 1
    failed = 2
    waiting = 3


class SpotSensorData(Base):
    __tablename__ = "spot_sensor_reading"
    read_id = Column(Integer, primary_key=True)
    read_timestamp = Column(DateTime(timezone=True), server_default=func.now())
    update_timestamp = Column(DateTime(timezone=True), onupdate=func.now())
    spot_id = Column(Integer, nullable=False)
    is_occupied = Column(Boolean, default=False)
    sent_status = Column(Enum(Status), default=Status.created)

    def add(self):
        session.add(self)
        session.commit()
        return self


Base.metadata.create_all(engine)
