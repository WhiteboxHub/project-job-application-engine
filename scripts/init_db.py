
import sys
import os

# Add project root to path
<<<<<<< HEAD
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
=======
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)
>>>>>>> bavish_dev

from data.db_connection import db
from config.settings import settings
from core.logger import logger

def init_database():
<<<<<<< HEAD
    """Initialize DuckDB database with schema and seed data"""
    try:
        logger.info("=" * 60)
        logger.info("Starting database initialization...")
=======
    """Initialize DuckDB database with schema and seed data from root"""
    try:
        logger.info("=" * 60)
        logger.info("Starting database initialization from root...")
>>>>>>> bavish_dev
        logger.info("=" * 60)
        
        # Get paths
        db_path = settings.DUCKDB_PATH
<<<<<<< HEAD
        schema_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'db',
            'schema.sql'
        )
=======
        schema_path = os.path.join(ROOT_DIR, 'db', 'schema.sql')
>>>>>>> bavish_dev
        
        # Check if schema file exists
        if not os.path.exists(schema_path):
            logger.error(f"Schema file not found: {schema_path}")
            return False
        
        logger.info(f"Database path: {db_path}")
        logger.info(f"Schema file: {schema_path}")
        
        # Execute schema SQL
        logger.info("Executing schema.sql...")
        success = db.execute_sql_file(schema_path)
        
        if success:
            logger.info("=" * 60)
            logger.info("✅ Database initialized successfully!")
            logger.info("=" * 60)
            logger.info("\nNext steps:")
<<<<<<< HEAD
            logger.info("1. Review database at: {db_path}")
            logger.info("2. Test with: python scripts/main.py --dry-run")
            logger.info("3. Check seeded data for Insight Global")
=======
            logger.info(f"1. Review database at: {db_path}")
            logger.info("2. Test with: python scripts/main.py --dry-run")
            logger.info("3. Check seeded data for KForce")
>>>>>>> bavish_dev
            return True
        else:
            logger.error("Failed to initialize database")
            return False
            
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    init_database()
