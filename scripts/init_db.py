import sys
import os
import argparse

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.db_mysql import db_mysql
from data.db_duck import db_duck
from models.config_models import Base as MysqlBase
from models.persistence_models import Base as DuckBase
from core.logger import logger

def init_db():
    logger.info("Initializing databases...")
    
    try:
        # MySQL
        logger.info("Creating MySQL tables...")
        MysqlBase.metadata.create_all(bind=db_mysql.engine)
        logger.info("MySQL tables created.")
        
        # DuckDB
        logger.info("Creating DuckDB tables...")
        DuckBase.metadata.create_all(bind=db_duck.engine)
        logger.info("DuckDB tables created.")
        
        logger.info("Database initialization complete.")
    except Exception as e:
        logger.critical(f"Database initialization failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    init_db()
