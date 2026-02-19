"""
Test Automation Flow - Verify MySQL Integration with Flag-Based Trigger

This script tests the complete workflow:
1. Check MySQL connection
2. Verify candidate_marketing table structure
3. Check for flagged candidates (marketing_flag = 1)
4. Verify run_parameters are populated
5. Test that Infosys and LanceSoft automation can be triggered
6. Run scheduler worker in dry-run mode

Usage:
    python scripts/test_automation_flow.py
"""
import mysql.connector
from mysql.connector import Error
import json
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def print_section(title):
    """Print formatted section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def test_mysql_connection():
    """Test MySQL connection"""
    print_section("1️⃣  TESTING MYSQL CONNECTION")
    
    try:
        connection = mysql.connector.connect(
            host='127.0.0.1',
            port=3306,
            user='root',
            password='M@hi14119866',
            database='new_db'
        )
        
        if connection.is_connected():
            db_info = connection.get_server_info()
            print(f"✅ Connected to MySQL Server version {db_info}")
            
            cursor = connection.cursor()
            cursor.execute("SELECT DATABASE();")
            record = cursor.fetchone()
            print(f"✅ Connected to database: {record[0]}")
            
            cursor.close()
            connection.close()
            return True
            
    except Error as e:
        print(f"❌ Error connecting to MySQL: {e}")
        return False

def check_table_structure():
    """Verify candidate_marketing table structure"""
    print_section("2️⃣  CHECKING CANDIDATE_MARKETING TABLE STRUCTURE")
    
    try:
        connection = mysql.connector.connect(
            host='127.0.0.1',
            port=3306,
            user='root',
            password='M@hi14119866',
            database='new_db'
        )
        
        cursor = connection.cursor(dictionary=True)
        
        # Check required columns
        cursor.execute("""
            SELECT COLUMN_NAME, DATA_TYPE 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = 'new_db' 
              AND TABLE_NAME = 'candidate_marketing'
            ORDER BY ORDINAL_POSITION
        """)
        
        columns = cursor.fetchall()
        
        print(f"\n📋 Found {len(columns)} columns:")
        required_columns = ['id', 'candidate_id', 'marketing_flag', 'is_processed', 
                           'status', 'run_parameters', 'resume_url']
        
        found_columns = [col['COLUMN_NAME'] for col in columns]
        
        for req_col in required_columns:
            if req_col in found_columns:
                col_type = next(c['DATA_TYPE'] for c in columns if c['COLUMN_NAME'] == req_col)
                print(f"   ✅ {req_col} ({col_type})")
            else:
                print(f"   ❌ {req_col} - MISSING!")
                return False
        
        cursor.close()
        connection.close()
        return True
        
    except Error as e:
        print(f"❌ Error checking table structure: {e}")
        return False

def check_flagged_candidates():
    """Check for candidates with marketing_flag = 1"""
    print_section("3️⃣  CHECKING FLAGGED CANDIDATES")
    
    try:
        connection = mysql.connector.connect(
            host='127.0.0.1',
            port=3306,
            user='root',
            password='M@hi14119866',
            database='new_db'
        )
        
        cursor = connection.cursor(dictionary=True)
        
        # Count flagged candidates
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM candidate_marketing
            WHERE marketing_flag = 1
        """)
        total_flagged = cursor.fetchone()['count']
        print(f"\n📊 Total candidates with marketing_flag = 1: {total_flagged}")
        
        # Count unprocessed flagged candidates
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM candidate_marketing
            WHERE marketing_flag = 1 
              AND is_processed = 0
        """)
        unprocessed = cursor.fetchone()['count']
        print(f"📊 Unprocessed candidates: {unprocessed}")
        
        # Count active unprocessed flagged candidates
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM candidate_marketing
            WHERE marketing_flag = 1 
              AND is_processed = 0
              AND status = 'active'
        """)
        active_unprocessed = cursor.fetchone()['count']
        print(f"📊 Active unprocessed candidates: {active_unprocessed}")
        
        if active_unprocessed == 0:
            print("\n⚠️  WARNING: No active candidates flagged for automation!")
            print("   To enable automation, run:")
            print("   UPDATE candidate_marketing SET marketing_flag = 1, is_processed = 0 WHERE id = <ID>;")
            return False
        
        # Show details of flagged candidates
        cursor.execute("""
            SELECT 
                cm.id,
                cm.candidate_id,
                c.full_name,
                c.email,
                cm.marketing_flag,
                cm.is_processed,
                cm.status,
                LENGTH(cm.run_parameters) as params_size
            FROM candidate_marketing cm
            JOIN candidate c ON cm.candidate_id = c.id
            WHERE cm.marketing_flag = 1 
              AND cm.is_processed = 0
              AND cm.status = 'active'
            LIMIT 5
        """)
        
        candidates = cursor.fetchall()
        
        print(f"\n📋 Active candidates ready for automation:")
        for idx, cand in enumerate(candidates, 1):
            print(f"\n   [{idx}] ID: {cand['id']}")
            print(f"       Name: {cand['full_name']}")
            print(f"       Email: {cand['email']}")
            print(f"       Status: {cand['status']}")
            print(f"       run_parameters: {'✅ Populated' if cand['params_size'] else '❌ Empty'}")
        
        cursor.close()
        connection.close()
        return True
        
    except Error as e:
        print(f"❌ Error checking flagged candidates: {e}")
        return False

def check_run_parameters():
    """Verify run_parameters are properly populated"""
    print_section("4️⃣  VERIFYING RUN_PARAMETERS")
    
    try:
        connection = mysql.connector.connect(
            host='127.0.0.1',
            port=3306,
            user='root',
            password='M@hi14119866',
            database='new_db'
        )
        
        cursor = connection.cursor(dictionary=True)
        
        # Get first flagged candidate with run_parameters
        cursor.execute("""
            SELECT 
                cm.id,
                c.full_name,
                cm.run_parameters
            FROM candidate_marketing cm
            JOIN candidate c ON cm.candidate_id = c.id
            WHERE cm.marketing_flag = 1 
              AND cm.is_processed = 0
              AND cm.status = 'active'
              AND cm.run_parameters IS NOT NULL
            LIMIT 1
        """)
        
        candidate = cursor.fetchone()
        
        if not candidate:
            print("❌ No candidates with run_parameters found!")
            print("   Run: python scripts/populate_run_parameters.py")
            return False
        
        print(f"\n✅ Found candidate: {candidate['full_name']} (ID: {candidate['id']})")
        
        # Parse run_parameters
        try:
            params = json.loads(candidate['run_parameters'])
            
            print("\n📋 run_parameters structure:")
            print(f"   ✅ search.keywords: {params.get('search', {}).get('keywords', 'MISSING')}")
            print(f"   ✅ search.location: {params.get('search', {}).get('location', 'MISSING')}")
            print(f"   ✅ applicant.first_name: {params.get('applicant', {}).get('first_name', 'MISSING')}")
            print(f"   ✅ applicant.email: {params.get('applicant', {}).get('email', 'MISSING')}")
            print(f"   ✅ resume_url: {params.get('resume_url', 'MISSING')[:50]}...")
            
            if 'parsed_resume' in params:
                skills_count = len(params['parsed_resume'].get('skills', []))
                print(f"   ✅ parsed_resume.skills: {skills_count} skills found")
            
            return True
            
        except json.JSONDecodeError as e:
            print(f"❌ Error parsing run_parameters JSON: {e}")
            return False
        
        cursor.close()
        connection.close()
        
    except Error as e:
        print(f"❌ Error checking run_parameters: {e}")
        return False

def check_fully_automatable_sites():
    """Check which sites are marked as fully automatable"""
    print_section("5️⃣  CHECKING FULLY AUTOMATABLE SITES")
    
    try:
        connection = mysql.connector.connect(
            host='127.0.0.1',
            port=3306,
            user='root',
            password='M@hi14119866',
            database='new_db'
        )
        
        cursor = connection.cursor(dictionary=True)
        
        # Get fully automatable sites
        cursor.execute("""
            SELECT 
                s.id,
                s.company_name,
                s.domain,
                s.is_active,
                p.name as platform_name,
                p.automation_level,
                p.class_handler
            FROM job_sites s
            JOIN ats_platforms p ON s.ats_platform_id = p.id
            WHERE p.automation_level = 'fully'
              AND s.is_active = 1
        """)
        
        sites = cursor.fetchall()
        
        if not sites:
            print("❌ No fully automatable sites found!")
            print("   Expected: Infosys, LanceSoft")
            return False
        
        print(f"\n✅ Found {len(sites)} fully automatable sites:")
        
        expected_sites = ['Infosys', 'LanceSoft']
        found_sites = [s['company_name'] for s in sites]
        
        for site in sites:
            status = "✅" if site['company_name'] in expected_sites else "⚠️"
            print(f"\n   {status} {site['company_name']}")
            print(f"       Domain: {site['domain']}")
            print(f"       Platform: {site['platform_name']}")
            print(f"       Automation: {site['automation_level']}")
            print(f"       Active: {'Yes' if site['is_active'] else 'No'}")
            print(f"       Handler: {site['class_handler']}")
        
        # Check if expected sites are present
        for expected in expected_sites:
            if expected not in found_sites:
                print(f"\n   ⚠️  WARNING: {expected} not found in fully automatable sites!")
        
        cursor.close()
        connection.close()
        return True
        
    except Error as e:
        print(f"❌ Error checking automatable sites: {e}")
        return False

def test_scheduler_query():
    """Test the exact query used by scheduler_worker.py"""
    print_section("6️⃣  TESTING SCHEDULER WORKER QUERY")
    
    try:
        connection = mysql.connector.connect(
            host='127.0.0.1',
            port=3306,
            user='root',
            password='M@hi14119866',
            database='new_db'
        )
        
        cursor = connection.cursor(dictionary=True)
        
        # This is the exact query from scheduler_worker.py
        query = """
            SELECT 
                cm.id as cm_id,
                cm.candidate_id,
                cm.run_parameters,
                c.full_name,
                c.email,
                s.id as site_id,
                s.company_name,
                s.domain,
                s.search_url_template,
                p.id as platform_id,
                p.name as platform_name,
                p.class_handler,
                p.automation_level
            FROM candidate_marketing cm
            JOIN candidate c ON cm.candidate_id = c.id
            CROSS JOIN job_sites s
            JOIN ats_platforms p ON s.ats_platform_id = p.id
            WHERE cm.marketing_flag = 1 
              AND cm.is_processed = 0
              AND cm.status = 'active'
              AND s.is_active = 1
              AND p.automation_level = 'fully'
            ORDER BY cm.candidate_id, s.id
        """
        
        cursor.execute(query)
        results = cursor.fetchall()
        
        print(f"\n✅ Scheduler query returned {len(results)} candidate × site combinations")
        
        if len(results) == 0:
            print("\n❌ No automation tasks found!")
            print("   This means the scheduler will not run any automation.")
            print("\n   To fix:")
            print("   1. Ensure marketing_flag = 1 in candidate_marketing")
            print("   2. Ensure is_processed = 0")
            print("   3. Ensure status = 'active'")
            print("   4. Ensure job_sites.is_active = 1")
            print("   5. Ensure ats_platforms.automation_level = 'fully'")
            return False
        
        # Group by candidate
        candidates_dict = {}
        for row in results:
            cand_id = row['candidate_id']
            if cand_id not in candidates_dict:
                candidates_dict[cand_id] = {
                    'name': row['full_name'],
                    'email': row['email'],
                    'sites': []
                }
            candidates_dict[cand_id]['sites'].append(row['company_name'])
        
        print(f"\n📋 Automation tasks breakdown:")
        for cand_id, info in candidates_dict.items():
            print(f"\n   👤 {info['name']} (ID: {cand_id})")
            print(f"      Email: {info['email']}")
            print(f"      Sites: {', '.join(info['sites'])}")
            print(f"      Total: {len(info['sites'])} site(s)")
        
        cursor.close()
        connection.close()
        return True
        
    except Error as e:
        print(f"❌ Error testing scheduler query: {e}")
        import traceback
        traceback.print_exc()
        return False

def print_next_steps():
    """Print next steps for testing"""
    print_section("🎯 NEXT STEPS")
    
    print("""
✅ All checks passed! You can now test the automation:

1️⃣  DRY-RUN TEST (Recommended first):
   python scripts/scheduler_worker.py --dry-run
   
   This will:
   - Open browser
   - Navigate to Infosys and LanceSoft
   - Extract job URLs
   - Fill forms (but NOT submit)
   - Close browser
   
2️⃣  SINGLE CANDIDATE TEST:
   python scripts/scheduler_worker.py --dry-run --candidate-id <ID>
   
   Test with just one candidate first
   
3️⃣  LIVE RUN (After dry-run succeeds):
   python scripts/scheduler_worker.py
   
   This will actually submit applications!
   
4️⃣  SCHEDULE IT:
   Once confirmed working, add to Windows Task Scheduler:
   - Trigger: Daily at specific time
   - Action: python scripts/scheduler_worker.py
   - Working directory: <project_root>

📝 MONITORING:
   - Logs: logs/automation/<date>/
   - Database: automation_logs table
   - Check: SELECT * FROM automation_logs ORDER BY timestamp DESC;

🔄 RE-ENABLE CANDIDATES:
   After processing, candidates are marked is_processed = 1
   To re-run for same candidate:
   UPDATE candidate_marketing SET is_processed = 0 WHERE id = <ID>;
""")

def main():
    """Run all tests"""
    print("\n" + "🔬" * 40)
    print("  TESTING MYSQL INTEGRATION WITH FLAG-BASED AUTOMATION")
    print("🔬" * 40)
    
    all_passed = True
    
    # Run tests
    all_passed &= test_mysql_connection()
    all_passed &= check_table_structure()
    all_passed &= check_flagged_candidates()
    all_passed &= check_run_parameters()
    all_passed &= check_fully_automatable_sites()
    all_passed &= test_scheduler_query()
    
    # Print summary
    print_section("📊 TEST SUMMARY")
    
    if all_passed:
        print("\n✅ ALL TESTS PASSED!")
        print_next_steps()
    else:
        print("\n❌ SOME TESTS FAILED!")
        print("\n   Please fix the issues above before running automation.")
        print("   Common fixes:")
        print("   - Run: python scripts/populate_run_parameters.py")
        print("   - Enable candidate: UPDATE candidate_marketing SET marketing_flag = 1 WHERE id = <ID>;")
        print("   - Reset processed: UPDATE candidate_marketing SET is_processed = 0 WHERE id = <ID>;")

if __name__ == "__main__":
    main()
