from sqlalchemy import Column, Integer, String, Boolean, Text, Enum, ForeignKey, JSON, MetaData
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
from sqlalchemy.dialects.mysql import TIMESTAMP as MySQLTimestamp

Base = declarative_base()
metadata = MetaData()

class TimeStampedModel(Base):
    __abstract__ = True
    created_at = Column(MySQLTimestamp, server_default="CURRENT_TIMESTAMP")
    updated_at = Column(MySQLTimestamp, server_default="CURRENT_TIMESTAMP", onupdate="CURRENT_TIMESTAMP")

class AtsPlatform(TimeStampedModel):
    __tablename__ = 'ats_platforms'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    class_handler = Column(String(100), nullable=False)
    is_headless_required = Column(Boolean, default=True)
    
    # Relationships
    job_sites = relationship("JobSite", back_populates="platform")
    selectors = relationship("SiteSelector", back_populates="platform")

class JobSite(TimeStampedModel):
    __tablename__ = 'job_sites'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    company_name = Column(String(100), nullable=False)
    domain = Column(String(255), unique=True, nullable=False)
    ats_platform_id = Column(Integer, ForeignKey('ats_platforms.id', ondelete='SET NULL'))
    category = Column(Enum('System integrator', 'Consulting firm', 'Staffing vendor', 'Product Company'), nullable=False)
    
    search_url_template = Column(Text, nullable=False)
    apply_url_template = Column(Text, nullable=True)
    
    cf_clearance_required = Column(Boolean, default=False)
    proxy_region = Column(String(10), default='US')
    is_active = Column(Boolean, default=True)
    
    # Relationships
    platform = relationship("AtsPlatform", back_populates="job_sites")
    selectors = relationship("SiteSelector", back_populates="site")
    listings = relationship("JobListing", back_populates="site")

class SiteSelector(Base):
    __tablename__ = 'site_selectors'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ats_platform_id = Column(Integer, ForeignKey('ats_platforms.id', ondelete='CASCADE'), nullable=True)
    job_site_id = Column(Integer, ForeignKey('job_sites.id', ondelete='CASCADE'), nullable=True)
    
    type = Column(Enum('listing', 'application'), nullable=False)
    config_json = Column(JSON, nullable=False)
    updated_at = Column(MySQLTimestamp, server_default="CURRENT_TIMESTAMP", onupdate="CURRENT_TIMESTAMP")
    
    # Relationships
    platform = relationship("AtsPlatform", back_populates="selectors")
    site = relationship("JobSite", back_populates="selectors")

class JobListing(TimeStampedModel):
    __tablename__ = 'job_listings'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    job_site_id = Column(Integer, ForeignKey('job_sites.id', ondelete='CASCADE'), nullable=False)
    
    external_job_id = Column(String(100), nullable=False)
    job_title = Column(String(255))
    job_url = Column(Text, nullable=False)
    
    status = Column(Enum('discovered', 'ready_to_apply', 'applied', 'failed', 'blacklisted'), default='discovered')
    attempts = Column(Integer, default=0)
    last_error = Column(Text)
    
    # Relationships
    site = relationship("JobSite", back_populates="listings")
