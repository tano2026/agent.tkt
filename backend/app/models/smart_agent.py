"""
Smart Agent Database Models — multi-tenant booking platform.

Models:
- Tenant: CTV/dai_ly/whitelabel account
- FlightBooking: vé máy bay bookings
- FastTrackOrder: Fast Track Nội Bài orders
- EsimOrder: eSIM du lịch orders
- VisaConsultation: visa/hộ chiếu tư vấn orders
- Payment: payment transaction log
"""

from __future__ import annotations

import logging
from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, Date,
    ForeignKey, Enum, create_engine, select, func
)
from sqlalchemy.orm import declarative_base

logger = logging.getLogger(__name__)

Base = declarative_base()


class Tenant(Base):
    """Multi-tenant CTV / agency account."""
    __tablename__ = "sa_tenants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_name = Column(String(200), nullable=False)
    full_name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=False, unique=True)
    email = Column(String(200), nullable=False)
    business_type = Column(String(50), default="ctv")  # ctv | dai_ly | whitelabel
    agent_tier = Column(String(20), default="free")  # free | pro | whitelabel
    api_key = Column(String(64), unique=True, nullable=False)
    balance = Column(Float, default=0.0)
    commission_rate = Column(Float, default=0.08)
    monthly_booking_limit = Column(Integer, default=50)
    booking_count = Column(Integer, default=0)
    status = Column(String(20), default="active")  # active | suspended | cancelled
    registered_at = Column(DateTime, default=datetime.utcnow)
    subscription_expires_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)


class FlightBooking(Base):
    """Flight ticket booking record."""
    __tablename__ = "sa_flight_bookings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("sa_tenants.id"), nullable=False)
    booking_code = Column(String(50), nullable=False, unique=True)
    airline = Column(String(50), nullable=False)
    route = Column(String(100), nullable=False)  # e.g. "HAN→SGN"
    depart_date = Column(Date, nullable=False)
    return_date = Column(Date, nullable=True)
    pax_count = Column(Integer, default=1)
    total_price = Column(Float, nullable=False)
    commission = Column(Float, default=0)
    status = Column(String(20), default="pending")  # pending | confirmed | cancelled | completed
    passenger_name = Column(String(200), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class FastTrackOrder(Base):
    """Fast Track / VIP Lounge Nội Bài orders."""
    __tablename__ = "sa_fasttrack_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("sa_tenants.id"), nullable=False)
    passenger = Column(String(100), nullable=False)
    customer_phone = Column(String(20), nullable=False)
    flight_date = Column(Date, nullable=False)
    flight_number = Column(String(20), nullable=False)
    pax_count = Column(Integer, default=1)
    service_type = Column(String(20), default="fasttrack")  # fasttrack | vip_lounge
    total_price = Column(Float, nullable=False)
    commission = Column(Float, default=0)
    status = Column(String(20), default="pending")  # pending | confirmed | completed | cancelled
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class EsimOrder(Base):
    """eSIM travel eSIM orders."""
    __tablename__ = "sa_esim_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("sa_tenants.id"), nullable=False)
    package_code = Column(String(50), nullable=False)
    customer_phone = Column(String(20), nullable=False)
    customer_email = Column(String(200), nullable=True)
    destination = Column(String(100), nullable=False)
    duration_days = Column(Integer, default=7)
    total_price = Column(Float, nullable=False)
    commission = Column(Float, default=0)
    esim_qr = Column(Text, nullable=True)
    status = Column(String(20), default="pending")  # pending | delivered | completed
    created_at = Column(DateTime, default=datetime.utcnow)


class VisaConsultation(Base):
    """Visa / hộ chiếu consultation requests."""
    __tablename__ = "sa_visa_consultations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("sa_tenants.id"), nullable=False)
    customer_name = Column(String(100), nullable=False)
    customer_phone = Column(String(20), nullable=False)
    country = Column(String(100), nullable=False)  # e.g. "Nhật Bản", "Hàn Quốc", "Schengen"
    passport = Column(String(50), nullable=True)  # passport number
    service_type = Column(String(20), default="visa")  # visa | hochieu
    total_price = Column(Float, default=0)
    commission = Column(Float, default=0)
    status = Column(String(20), default="pending")  # pending | processing | completed | rejected
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Payment(Base):
    """Payment transaction log — subscriptions + services."""
    __tablename__ = "sa_payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("sa_tenants.id"), nullable=False)
    order_type = Column(String(20), nullable=False)  # subscription | flight | fasttrack | esim | visa
    order_id = Column(Integer, nullable=False)
    amount = Column(Float, nullable=False)
    payment_method = Column(String(20), nullable=False)  # momo | vnpay | bank | cash
    transaction_id = Column(String(100), nullable=True)
    ref_code = Column(String(50), nullable=True)  # Mã tham chiếu giao dịch
    status = Column(String(20), default="pending")  # pending | completed | failed
    created_at = Column(DateTime, default=datetime.utcnow)
