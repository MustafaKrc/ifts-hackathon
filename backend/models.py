from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from database import Base


class CustomerJourney(Base):
    __tablename__ = "customer_journeys"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    segment = Column(String, nullable=False)
    region = Column(String, nullable=False)
    risk_score = Column(Integer, nullable=False)
    recommended_action = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
