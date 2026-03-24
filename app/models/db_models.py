"""
SQLAlchemy ORM models for PostgreSQL.
All persistent data — users, menu, orders, call logs.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text, DateTime,
    ForeignKey, JSON, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base

import enum


# ── Enums ─────────────────────────────────────────────────────────────────────

class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PREPARING = "preparing"
    READY = "ready"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class OrderType(str, enum.Enum):
    PICKUP = "pickup"
    DELIVERY = "delivery"
    DINE_IN = "dine_in"


class CallStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ABANDONED = "abandoned"


# ── User ──────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ── Menu ──────────────────────────────────────────────────────────────────────

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    display_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    items = relationship("MenuItemDB", back_populates="category", cascade="all, delete-orphan")


class MenuItemDB(Base):
    __tablename__ = "menu_items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    price = Column(Float, nullable=False)
    description = Column(Text, default="")
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    available = Column(Boolean, default=True)
    customisations = Column(JSON, default=list)  # list of strings
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    category = relationship("Category", back_populates="items")


# ── Orders ────────────────────────────────────────────────────────────────────

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String(200), default="Unknown")
    customer_phone = Column(String(20), nullable=False, index=True)
    order_type = Column(String(20), default=OrderType.PICKUP.value)
    status = Column(String(20), default=OrderStatus.PENDING.value)
    total = Column(Float, default=0.0)
    call_sid = Column(String(100), nullable=True, index=True)
    notes = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    items = relationship("OrderItemDB", back_populates="order", cascade="all, delete-orphan")


class OrderItemDB(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    menu_item_name = Column(String(200), nullable=False)
    quantity = Column(Integer, default=1)
    unit_price = Column(Float, default=0.0)
    notes = Column(String(500), default="")
    subtotal = Column(Float, default=0.0)

    order = relationship("Order", back_populates="items")


# ── Call Logs ─────────────────────────────────────────────────────────────────

class CallLog(Base):
    __tablename__ = "call_logs"

    id = Column(Integer, primary_key=True, index=True)
    call_sid = Column(String(100), unique=True, nullable=False, index=True)
    phone_number = Column(String(20), nullable=False, index=True)
    customer_name = Column(String(200), default="Unknown")
    status = Column(String(20), default=CallStatus.IN_PROGRESS.value)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, default=0)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)

    messages = relationship("CallMessage", back_populates="call_log", cascade="all, delete-orphan",
                            order_by="CallMessage.timestamp")


class CallMessage(Base):
    __tablename__ = "call_messages"

    id = Column(Integer, primary_key=True, index=True)
    call_log_id = Column(Integer, ForeignKey("call_logs.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)  # "system", "user", "assistant"
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    call_log = relationship("CallLog", back_populates="messages")
