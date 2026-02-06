import duckdb
import os
try:
    from tabulate import tabulate
except ImportError:
    tabulate = None

DB_PATH = os.path.join(os.getcwd(), "data", "selectors.duckdb")

def view_submitted_jobs():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at: {DB_PATH}")
        return

    try:
        conn = duckdb.connect(DB_PATH, read_only=True)
        # Check if table exists
        tables = conn.execute("SHOW TABLES").fetchall()
        if ('submitted_jobs',) not in tables:
            print("Table 'submitted_jobs' does not exist yet.")
            return

        rows = conn.execute("SELECT * FROM submitted_jobs ORDER BY applied_at DESC").fetchall()
        headers = ["Job ID", "Job Title", "Applied At"]
        
        print(f"\n--- Submitted Jobs ({len(rows)}) ---\n")
        try:
            print(tabulate(rows, headers=headers, tablefmt="grid"))
        except ImportError:
            # Fallback if tabulate is not installed
            print(f"{' | '.join(headers)}")
            print("-" * 50)
            for row in rows:
                print(f"{row[0]} | {row[1]} | {row[2]}")
                
    except Exception as e:
        print(f"Error reading database: {e}")

if __name__ == "__main__":
    view_submitted_jobs()
