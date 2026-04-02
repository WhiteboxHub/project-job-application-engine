import requests
import json
import os
import sys

# Ensure project root is in path to use settings/backend_client if needed
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.settings import settings
from core.backend_client import _api_headers

def update_backend_schedule():
    schedule_id = 7
    base = settings.BACKEND_URL.rstrip("/")
    url = f"{base}/automation-workflow-schedule/{schedule_id}"
    
    payload = {
        "frequency": "daily",
        "cron": "30 9 * * *",
        "interval": 1
    }
    
    headers = _api_headers(json_body=True)
    
    print(f"Updating backend schedule {schedule_id} at {url}...")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.put(url, headers=headers, json=payload, timeout=15)
        if response.status_code == 200:
            print("Successfully updated backend schedule to DAILY at 09:30 AM!")
            print("Response:", response.json())
        else:
            print(f"Failed to update schedule. Status {response.status_code}: {response.text}")
    except Exception as e:
        print(f"Error during API call: {e}")

if __name__ == "__main__":
    update_backend_schedule()
