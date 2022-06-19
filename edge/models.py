import enum, json
from sqlalchemy import Column, Integer, DateTime, Boolean, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


engine = create_engine('sqlite:///sqlite.db', echo=True)
Session = sessionmaker(bind=engine)
# create a Session
session = Session()

Base = declarative_base()


class Status(enum.Enum):
    created = 0
    processed = 1
    failed = 2
    waiting = 3


class SpotSensorData(Base):
    __tablename__ = "spot_sensor_reading"
    read_id = Column(Integer, primary_key=True)
    read_timestamp = Column(DateTime(timezone=True), server_default=func.now())
    update_timestamp = Column(DateTime(timezone=True), onupdate=func.now())
    spot_id = Column(Integer, nullable=False)
    is_occupied = Column(Boolean, default=False)
    sent_status = Column(Enum(Status),default=Status.created)

    def add(self):
        session.add(self)
        session.commit()
        return self

    @staticmethod
    def get_last_n_readings(n):
        return session.query(SpotSensorData).filter(SpotSensorData.sent_status==Status.created).limit(n).all()

    @staticmethod
    def set_to_processed(last_read_id):
        session.query(SpotSensorData).filter(SpotSensorData.read_id <= last_read_id).update({"sent_status": Status.processed})
        session.commit()

    @staticmethod
    def encode_query(query):
        summary_dict = {'0': [], '1': [], '2': [], '3': [], '4': [], '5': []}
        for reading in query:
            spot_id = reading.spot_id
            summary_dict[str(spot_id)].append(
                [{'datetime': reading.read_timestamp, 'is_occupied': reading.is_occupied}])
        return json.dumps(summary_dict, default=str).encode()


Base.metadata.create_all(engine)
