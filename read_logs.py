
import os

log_file = "comprehensive_dry_run_v2.txt"
if os.path.exists(log_file):
    with open(log_file, "rb") as f:
        content = f.read()
    
    text = content.decode("utf-16")
    print("--- FULL LOG CONTENT ---")
    print(text)
else:
    print(f"File {log_file} not found")
