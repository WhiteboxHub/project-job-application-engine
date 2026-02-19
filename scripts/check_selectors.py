
import os
import sys
import mysql.connector

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings

def check_selectors():
    try:
        conn = mysql.connector.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database=settings.DB_NAME
        )
        cursor = conn.cursor(dictionary=True)
        
        print("--- Checking Selectors for Infosys ---")
        # Get Job Site ID for Infosys
        cursor.execute("SELECT id, site_name FROM job_sites WHERE site_name LIKE '%Infosys%'")
        site = cursor.fetchone()
        
        if not site:
            print("❌ Infosys site not found in job_sites table.")
            return

        site_id = site['id']
        print(f"✅ Found Infosys Site ID: {site_id}")
        
        # Get Selectors
        cursor.execute(f"SELECT selector_name, selector_value, selector_type FROM site_selectors WHERE job_site_id = {site_id}")
        rows = cursor.fetchall()
        
        if not rows:
            print("❌ No selectors found in DB for Infosys.")
        else:
            print(f"✅ Found {len(rows)} selectors:")
            for row in rows:
                print(f"  - {row['selector_name']} ({row['selector_type']}): {row['selector_value']}")
                
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_selectors()
