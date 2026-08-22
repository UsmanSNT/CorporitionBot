from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, BigInteger, Boolean, DateTime,
    Float, Text, ForeignKey, UniqueConstraint, JSON
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_user_id = Column(BigInteger, unique=True, nullable=False)
    telegram_chat_id = Column(BigInteger, nullable=False)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    watch_rules = relationship("WatchRule", back_populates="user")
    notifications = relationship("Notification", back_populates="user")


class WatchRule(Base):
    __tablename__ = "watch_rules"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    keyword = Column(String(255), nullable=False)
    max_price = Column(BigInteger, nullable=True)
    min_price = Column(BigInteger, nullable=True)
    min_quantity = Column(Integer, nullable=True)
    max_quantity = Column(Integer, nullable=True)
    region = Column(String(255), nullable=True)
    seller = Column(String(255), nullable=True)
    category = Column(String(255), nullable=True)
    mxik = Column(String(100), nullable=True)
    tif_tn = Column(String(100), nullable=True)
    source = Column(String(50), nullable=True)  # "cooperation", "new_cooperation", None=both
    enabled = Column(Boolean, default=True)
    notify_new = Column(Boolean, default=True)
    notify_price_drop = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="watch_rules")
    notifications = relationship("Notification", back_populates="watch_rule")


class Listing(Base):
    __tablename__ = "listings"

    id = Column(Integer, primary_key=True)
    source = Column(String(50), nullable=False)
    external_id = Column(String(255), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(255), nullable=True)
    price = Column(BigInteger, nullable=True)
    currency = Column(String(20), nullable=True, default="UZS")
    quantity = Column(Integer, nullable=True)
    minimum_quantity = Column(Integer, nullable=True)
    seller_name = Column(String(500), nullable=True)
    seller_id = Column(String(255), nullable=True)
    region = Column(String(255), nullable=True)
    mxik = Column(String(100), nullable=True)
    tif_tn = Column(String(100), nullable=True)
    published_at = Column(DateTime, nullable=True)
    source_updated_at = Column(DateTime, nullable=True)
    source_url = Column(String(1000), nullable=True)
    image_url = Column(String(1000), nullable=True)
    raw_data_hash = Column(String(64), nullable=True)
    first_seen_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_source_external_id"),
    )

    price_history = relationship("PriceHistory", back_populates="listing")
    notifications = relationship("Notification", back_populates="listing")


class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True)
    listing_id = Column(Integer, ForeignKey("listings.id"), nullable=False)
    price = Column(BigInteger, nullable=True)
    recorded_at = Column(DateTime, default=datetime.utcnow)

    listing = relationship("Listing", back_populates="price_history")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    watch_rule_id = Column(Integer, ForeignKey("watch_rules.id"), nullable=True)
    listing_id = Column(Integer, ForeignKey("listings.id"), nullable=False)
    notification_type = Column(String(50), nullable=False)  # "new", "price_drop"
    price = Column(BigInteger, nullable=True)
    sent_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="notifications")
    watch_rule = relationship("WatchRule", back_populates="notifications")
    listing = relationship("Listing", back_populates="notifications")


class SystemState(Base):
    __tablename__ = "system_state"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
