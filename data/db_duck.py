from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from config.settings import settings
import logging
import os

logger = logging.getLogger(__name__)

class DuckDBConnection:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DuckDBConnection, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        # Ensure directory exists
        db_path = settings.DUCKDB_PATH
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        try:
            # DuckDB SQLAlchemy url: duckdb:///path/to/file
            self.engine = create_engine(f"duckdb:///{db_path}")
            self.SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=self.engine))
            logger.info(f"DuckDB Engine initialized at {db_path}.")
        except Exception as e:
            logger.critical(f"Failed to initialize DuckDB engine: {e}")
            raise

    def get_session(self):
        session = self.SessionLocal()
        try:
            yield session
        finally:
            session.close()

db_duck = DuckDBConnection()
