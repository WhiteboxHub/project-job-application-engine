from sqlalchemy import Column, Integer, String, Text, DateTime, Float
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class Application(Base):
    __tablename__ = 'applications'
    
    # Composite PK could be used, but simple ID is fine for log
    run_id = Column(String(64), primary_key=True) 
    job_id = Column(String(100), primary_key=True)
    status = Column(String(50))
    timestamp = Column(DateTime, default=datetime.utcnow)
    screenshot_path = Column(Text)

class Metric(Base):
    __tablename__ = 'metrics'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), index=True)
    step_name = Column(String(100))
    retry_count = Column(Integer, default=0)
    error_msg = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
