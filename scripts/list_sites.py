import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.db_mysql import db_mysql
from models.config_models import JobSite

def list_sites():
    session = db_mysql.SessionLocal()
    try:
        sites = session.query(JobSite).all()
        print(f"Found {len(sites)} sites:")
        for s in sites:
            print(f"- ID: {s.id} | Name: '{s.company_name}' | Active: {s.is_active}")
    finally:
        session.close()

if __name__ == "__main__":
    list_sites()
