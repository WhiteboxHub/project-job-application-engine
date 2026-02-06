from data.db_duckdb import db_duckdb
from data.db_mysql import db_mysql
import json

def test():
    print("Initializing DuckDB...")
    mysql_session = db_mysql.SessionLocal()
    try:
        db_duckdb.sync_from_mysql(mysql_session)
    finally:
        mysql_session.close()
    
    print("Testing selector fetch...")
    # Try fetching for Infosys (assuming job_site_id=1 or 2, checking common ones)
    for i in range(1, 5):
        sel = db_duckdb.get_selectors(job_site_id=i)
        print(f"Selectors for site {i}: {len(sel)} items")

if __name__ == "__main__":
    test()
