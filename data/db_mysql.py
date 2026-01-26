from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

class MySQLConnection:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MySQLConnection, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        try:
            self.engine = create_engine(
                settings.mysql_url,
                pool_pre_ping=True,
                pool_recycle=3600,
                json_serializer=lambda obj: obj  # Pass-through for JSON types if needed
            )
            self.SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=self.engine))
            logger.info("MySQL Engine initialized.")
        except Exception as e:
            logger.critical(f"Failed to initialize MySQL engine: {e}")
            raise

    def get_session(self):
        """Metadata for dependency injection or context managers"""
        session = self.SessionLocal()
        try:
            yield session
        finally:
            session.close()

db_mysql = MySQLConnection()
