"""
Quick DuckDB Query Tool
Run SQL queries against the job_engine.duckdb database
"""

import duckdb
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings

def run_query(sql_query):
    """Run a SQL query and display results"""
    try:
        conn = duckdb.connect(settings.DUCKDB_PATH)
        
        print("=" * 70)
        print(f"QUERY: {sql_query}")
        print("=" * 70)
        
        rows = conn.execute(sql_query).fetchall()
        columns = [desc[0] for desc in conn.execute(f"DESCRIBE {sql_query.split(' ')[sql_query.lower().split(' ').index('from') + 1]}").fetchall()] if "from" in sql_query.lower() else []
        
        if not rows:
            print("\n❌ No results found")
        else:
            print(f"\n✅ Found {len(rows)} row(s):\n")
            if columns:
                print(" | ".join(columns))
                print("-" * 70)
            for row in rows:
                print(" | ".join(str(val) for val in row))
        
        conn.close()
        print("\n" + "=" * 70)
        
    except Exception as e:
        print(f"❌ Query failed: {e}")

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
            
            if query.lower() in ['exit', 'quit', 'q']:
                print("Goodbye!")
                break
            
            if query:
                run_query(query)
