"""
MySQL Connection Manager (Singleton Pattern)
Handles all database connections for both configuration and history.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

# Base class for ORM models
Base = declarative_base()

class MySQLConnection:
    """Singleton connection manager for MySQL"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MySQLConnection, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize MySQL connection and session factory"""
        try:
            # URL encode password to handle special characters
            from urllib.parse import quote_plus
            encoded_password = quote_plus(settings.DB_PASSWORD)
            
            # Create MySQL connection URL
            # Format: mysql+pymysql://user:password@host:port/database
            db_url = (
                f"mysql+pymysql://{settings.DB_USER}:{encoded_password}"
                f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
            )
            
            self.engine = create_engine(
                db_url,
                echo=False,  # Set to True for SQL debugging
                pool_pre_ping=True,  # Verify connections before using
                pool_recycle=3600,   # Recycle connections after 1 hour
                connect_args={
                    'charset': 'utf8mb4',
                    'connect_timeout': 10
                }
            )
            
            # Create session factory
            self.SessionLocal = scoped_session(
                sessionmaker(
                    autocommit=False,
                    autoflush=False,
                    bind=self.engine
                )
            )
            
            logger.info(f"MySQL connection initialized: {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
            
        except Exception as e:
            logger.critical(f"Failed to initialize MySQL connection: {e}")
            raise
    
    def get_session(self):
        """Get a new database session"""
        return self.SessionLocal()
    
    def close_session(self, session):
        """Close a database session"""
        if session:
            session.close()
    
    def test_connection(self):
        """Test database connection"""
        try:
            session = self.get_session()
            session.execute(text("SELECT 1"))
            session.close()
            logger.info("MySQL connection test successful")
            return True
        except Exception as e:
            logger.error(f"MySQL connection test failed: {e}")
            return False

# Singleton instance
db = MySQLConnection()

