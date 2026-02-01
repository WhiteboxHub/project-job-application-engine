
import sys
import os
from sqlalchemy import text

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.db_mysql import db_mysql
from core.logger import logger

def seed_db():
    sql_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'db', 'sql')
    
    if not os.path.exists(sql_file_path):
        logger.error(f"SQL file not found at {sql_file_path}")
        return

    logger.info("Reading SQL seed file...")
    with open(sql_file_path, 'r') as f:
        sql_content = f.read()

    # Split by semicolon to handle multiple statements if needed, 
    # but sqlalchemy execute might handle it or we might need to parse.
    # A simple approach for this specific file structure (mostly Create/Insert).
    
    # Alternatively, use raw connection for multi-statement support if sqlalchemy struggles.
    
    connection = db_mysql.engine.raw_connection()
    try:
        cursor = connection.cursor()
        # MySQL connector usually allows multi=True or executing script
        # checking if we can just execute the whole thing
        logger.info("Executing SQL script...")
        # Current file has DELIMITER adjustments? No.
        # It has comments and standard statements.
        
        # Simple iterator for statements based on ;
        statements = sql_content.split(';')
        for statement in statements:
            stmt = statement.strip()
            if stmt:
                try:
                    cursor.execute(stmt)
                except Exception as e:
                    logger.warning(f"Statement failed: {e}")
                    
        connection.commit()
        logger.info("Database seeded successfully.")
    except Exception as e:
        logger.critical(f"Seeding failed: {e}")
    finally:
        connection.close()

if __name__ == "__main__":
    seed_db()
