"""
Quick DuckDB Query Tool
Run SQL queries against the job_engine.duckdb database
"""

import os
import sys

import duckdb

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings


def run_query(sql_query):
    """Run a SQL query and display results — no pandas required"""
    try:
        conn = duckdb.connect(settings.DUCKDB_PATH)

        print("=" * 70)
        print(f"QUERY: {sql_query}")
        print("=" * 70)

        cursor = conn.execute(sql_query)
        rows = cursor.fetchall()

        if not rows:
            print("\n  (no results)")
        else:
            # Get column names from cursor description
            cols = [d[0] for d in cursor.description] if cursor.description else []

            # Calculate column widths
            widths = [len(c) for c in cols]
            for row in rows:
                for i, val in enumerate(row):
                    widths[i] = max(widths[i], len(str(val)))

            # Print header
            header = "  ".join(c.ljust(widths[i]) for i, c in enumerate(cols))
            sep = "  ".join("-" * w for w in widths)
            print(f"\n{header}")
            print(sep)
            for row in rows:
                print("  ".join(str(v).ljust(widths[i]) for i, v in enumerate(row)))

            print(f"\n[OK] {len(rows)} row(s) returned.")

        conn.close()
        print("=" * 70)

    except Exception as e:
        print(f"[ERROR] Query failed: {e}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Query provided as command line argument
        query = " ".join(sys.argv[1:])
        run_query(query)
    else:
        # Interactive mode
        print("=" * 70)
        print("DuckDB Query Tool")
        print("=" * 70)
        print("\nCommon queries:")
        print("  1. SELECT * FROM job_sites WHERE is_active = true")
        print("  2. SELECT * FROM job_listings LIMIT 10")
        print("  3. SELECT * FROM applications ORDER BY applied_at DESC LIMIT 10")
        print("  4. SELECT status, COUNT(*) FROM job_listings GROUP BY status")
        print("\nEnter your SQL query (or 'exit' to quit):")

        while True:
            query = input("\nSQL> ").strip()

            if query.lower() in ["exit", "quit", "q"]:
                print("Goodbye!")
                break

            if query:
                run_query(query)
