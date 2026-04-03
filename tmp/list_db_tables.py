import duckdb
from data.db_connection import db

def list_tables():
    try:
        # Get DuckDB tables correctly
        tables = db.execute("SHOW TABLES").fetchall()
        print("--- Tables in DuckDB ---")
        for table in tables:
            table_name = table[0]
            print(f"Table: {table_name}")
            # Show columns
            columns = db.execute(f"DESCRIBE {table_name}").fetchall()
            for col in columns:
                print(f"  - {col[0]} ({col[1]})")
            print("\n")
            
    except Exception as e:
        print(f"Error querying DuckDB: {e}")

if __name__ == "__main__":
    list_tables()
