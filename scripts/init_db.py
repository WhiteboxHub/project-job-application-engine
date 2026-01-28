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
        
        # Load seed data from SQL file
        logger.info("Loading seed data...")
        sql_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'db', 'sql')
        
        if os.path.exists(sql_file_path):
            from sqlalchemy import text
            
            with open(sql_file_path, 'r', encoding='utf-8') as f:
                sql_content = f.read()
            
            # Split by semicolons and execute each statement
            # Filter out empty statements and comments
            statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip() and not stmt.strip().startswith('--')]
            
            with db_mysql.engine.connect() as conn:
                for statement in statements:
                    # Skip SET commands and other MySQL-specific commands that might cause issues
                    if statement.upper().startswith(('SET ', 'DROP TABLE', 'CREATE TABLE', 'INSERT INTO', 'ON DUPLICATE')):
                        try:
                            conn.execute(text(statement))
                            conn.commit()
                        except Exception as e:
                            logger.warning(f"Statement execution warning (may be expected): {e}")
            
            logger.info("Seed data loaded successfully.")
        else:
            logger.warning(f"SQL seed file not found at {sql_file_path}")
        
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
