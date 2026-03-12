"""
DuckDB Connection Manager (Singleton Pattern)
Replaces MySQL — uses a local DuckDB file for all job tracking.
"""

import logging
import os

import duckdb
from sqlalchemy.orm import declarative_base

from config.settings import settings

logger = logging.getLogger(__name__)

# Keep Base here so models that import it still work
Base = declarative_base()


class DuckDBConnection:
    """Singleton DuckDB connection manager"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DuckDBConnection, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize DuckDB connection"""
        try:
            db_path = settings.DUCKDB_PATH
            if db_path.startswith("md:"):
                # Connect to MotherDuck Cloud
                logger.info("Connecting to MotherDuck Cloud...")
                # DuckDB 0.9.0+ handles ?motherduck_token= appended to the URL automatically
                token_suffix = (
                    f"?motherduck_token={settings.MOTHERDUCK_TOKEN}"
                    if settings.MOTHERDUCK_TOKEN
                    else ""
                )
                self.conn = duckdb.connect(f"{db_path}{token_suffix}")
            else:
                # Ensure directory exists
                os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
                self.conn = duckdb.connect(db_path)
            logger.info(f"DuckDB connection initialized: {db_path}")
        except Exception as e:
            logger.critical(f"Failed to initialize DuckDB connection: {e}")
            raise

    def get_connection(self):
        """Get the DuckDB connection"""
        return self.conn

    def get_session(self):
        """Compatibility alias — returns raw DuckDB connection"""
        return self.conn

    def execute(self, query, params=None):
        """Execute a raw query"""
        if params:
            return self.conn.execute(query, params)
        return self.conn.execute(query)

    def test_connection(self):
        """Test database connection"""
        try:
            self.conn.execute("SELECT 1")
            logger.info("DuckDB connection test successful")
            return True
        except Exception as e:
            logger.error(f"DuckDB connection test failed: {e}")
            return False


class _LazyDB:
    """
    Lazy proxy for DuckDBConnection.

    On Windows, Python's multiprocessing uses the 'spawn' start method, which
    re-imports every module (including this one) in each worker process.  If we
    eagerly create a DuckDBConnection at import time the worker will try to open
    the already-locked .duckdb file and crash.

    This proxy defers the real connection until the first method call, so
    subprocesses that only import (but never query) the database never touch
    the file.
    """

    _db = None

    def _get(self):
        if self._db is None:
            self._db = DuckDBConnection()
        return self._db

    def get_connection(self):
        return self._get().get_connection()

    def get_session(self):
        return self._get().get_session()

    def execute(self, query, params=None):
        return self._get().execute(query, params)

    def test_connection(self):
        return self._get().test_connection()


# Lazy singleton — safe to import from worker/subprocess contexts
db = _LazyDB()
