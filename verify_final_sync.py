import requests
import os
import sys

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.settings import settings
from core.backend_client import _api_headers

def verify_backend_schedule():
    schedule_id = 7
    base = settings.BACKEND_URL.rstrip("/")
    url = f"{base}/automation-workflow-schedule/{schedule_id}"
    
    headers = _api_headers(json_body=False)
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            data = response.json()
            print("Backend Schedule Info:")
            print(f"  ID: {data.get('id')}")
            print(f"  Frequency: {data.get('frequency')}")
            print(f"  Cron: {data.get('cron')}")
            print(f"  Status: {data.get('status')}")
            print(f"  Next Run (Backend View): {data.get('next_run_at')}")
        else:
            print(f"Failed to fetch schedule. Status {response.status_code}: {response.text}")
    except Exception as e:
        print(f"Error checking backend: {e}")

if __name__ == "__main__":
    verify_backend_schedule()
