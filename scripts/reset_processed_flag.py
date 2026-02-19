"""
Reset is_processed flag for testing
"""
import pymysql

conn = pymysql.connect(
    host='127.0.0.1',
    port=3306,
    user='root',
    password='M@hi14119866',
    database='new_db'
)

cursor = conn.cursor()

print("Resetting is_processed for candidates with marketing_flag = 1...")

# Reset is_processed
cursor.execute("""
    UPDATE candidate_marketing 
    SET is_processed = 0,
        status = 'active'
    WHERE marketing_flag = 1
""")

conn.commit()
print(f"✅ Reset {cursor.rowcount} candidate(s)")

# Show what we have now
cursor.execute("""
    SELECT cm.id, cm.candidate_id, cm.marketing_flag, cm.is_processed, cm.status
    FROM candidate_marketing cm
    WHERE cm.marketing_flag = 1
""")

results = cursor.fetchall()

print()
print("=" * 70)
print("ENABLED CANDIDATES (Ready for scheduler)")
print("=" * 70)

for row in results:
    cm_id, cand_id, flag, processed, status = row
    print(f"candidate_id: {cand_id}, status: {status}, is_processed: {processed}")

print("=" * 70)
print()
print("Now test with:")
print("  python scripts/scheduler_worker.py --dry-run")

cursor.close()
conn.close()
