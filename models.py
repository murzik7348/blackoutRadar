"""Database models."""
from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import declarative_base, relationship


Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, nullable=False, unique=True, index=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    region_code = Column(String, nullable=False)
    region_title = Column(String, nullable=False)
    locality_id = Column(String, nullable=False)
    locality_title = Column(String, nullable=False)
    queue = Column(String, nullable=False)
    timezone = Column(String, nullable=False, default="Europe/Kyiv")
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())

    notifications = relationship("NotificationLog", back_populates="user", cascade="all, delete-orphan")


class OutageEvent(Base):
    __tablename__ = "outage_events"
    __table_args__ = (
        UniqueConstraint("region_code", "locality_id", "queue", "start_time", name="uq_event_identity"),
    )

    id = Column(Integer, primary_key=True)
    region_code = Column(String, nullable=False, index=True)
    region_title = Column(String, nullable=False)
    locality_id = Column(String, nullable=False, index=True)
    locality_title = Column(String, nullable=False)
    queue = Column(String, nullable=False, index=True)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    source_event_id = Column(String, nullable=True)
    fetched_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    notifications = relationship("NotificationLog", back_populates="event", cascade="all, delete-orphan")


class NotificationLog(Base):
    __tablename__ = "notification_log"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_notification_sent_once"),
    )

    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("outage_events.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    event = relationship("OutageEvent", back_populates="notifications")
    user = relationship("User", back_populates="notifications")
