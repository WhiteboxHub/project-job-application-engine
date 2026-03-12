"""
SQLAlchemy ORM Models — Application History
Database: DuckDB (file-based)
"""

from sqlalchemy import Column, Integer, String, Boolean, Text, Enum, ForeignKey, JSON, DateTime
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
from data.db_connection import Base


class Application(Base):
    __tablename__ = 'applications'

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_listing_id = Column(Integer, ForeignKey('job_listings.id', ondelete='CASCADE'), nullable=False)

    # Application state
    status = Column(Enum('pending', 'submitted', 'failed', 'cancelled'), default='pending')
    submission_attempts = Column(Integer, default=0)
    last_error = Column(Text)

    # Application data
    application_data = Column(JSON)
    submitted_at = Column(DateTime)

    # Tracking
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    job_listing = relationship("JobListing", backref="applications")


class Metric(Base):
    __tablename__ = 'metrics'

    id = Column(Integer, primary_key=True, autoincrement=True)
    metric_type = Column(String(50), nullable=False)
    metric_value = Column(String(255))
    metric_data = Column(JSON)

    # Tracking
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)