import sys
import os
sys.path.append(os.getcwd())

from data.db_mysql import db_mysql
from models.config_models import JobListing

def reset_listings():
    session = db_mysql.SessionLocal()
    try:
        # We want to reset both 'applied' and 'failed' to 'discovered' 
        # so the engine tries them again for the new profile.
        count = session.query(JobListing).filter(
            JobListing.status.in_(['applied', 'failed'])
        ).update({JobListing.status: 'discovered'}, synchronize_session=False)
        
        session.commit()
        print(f"Successfully reset {count} job listings to 'discovered'.")
    except Exception as e:
        print(f"Error resetting listings: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    reset_listings()
