"""
Test script to verify the project setup is working correctly.
Run this after setting up the database to check if everything is configured properly.
"""

import sys
import os

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")
    try:
        from config.settings import settings
        print("PASS: config.settings imported")
        
        from core.browser import browser_service
        print("PASS: core.browser imported")
        
        from core.safe_actions import SafeActions
        print("PASS: core.safe_actions imported")
        
        from core.logger import logger
        print("PASS: core.logger imported")
        
        from engine.factory import strategy_factory
        print("PASS: engine.factory imported")
        
        from engine.runner import EngineRunner
        print("PASS: engine.runner imported")
        
        from engine.guards import guards
        print("PASS: engine.guards imported")
        
        from strategies.base import BaseStrategy
        print("PASS: strategies.base imported")
        
        from models.config_models import JobSite, AtsPlatform
        print("PASS: models.config_models imported")
        
        from data.db_mysql import db_mysql
        print("PASS: models.db_mysql imported")
        
        from data.db_duck import db_duck
        print("PASS: data.db_duck imported")
        
        return True
    except Exception as e:
        print(f"FAIL: Import failed: {e}")
        return False

def test_settings():
    """Test that settings are loaded correctly"""
    print("\nTesting settings...")
    try:
        from config.settings import settings
        
        print(f"  DB_HOST: {settings.DB_HOST}")
        print(f"  DB_PORT: {settings.DB_PORT}")
        print(f"  DB_USER: {settings.DB_USER}")
        print(f"  DB_NAME: {settings.DB_NAME}")
        print(f"  DUCKDB_PATH: {settings.DUCKDB_PATH}")
        print(f"  CHROME_USER_DATA_DIR: {settings.CHROME_USER_DATA_DIR}")
        print(f"  HEADLESS: {settings.HEADLESS}")
        print(f"  MAX_APPLICATIONS_PER_RUN: {settings.MAX_APPLICATIONS_PER_RUN}")
        print(f"  DRY_RUN: {settings.DRY_RUN}")
        
        if settings.DB_PASSWORD == "YOUR_MYSQL_PASSWORD_HERE":
            print("WARNING: DB_PASSWORD is still set to placeholder. Update .env file!")
            return False
        
        print("PASS: Settings loaded successfully")
        return True
    except Exception as e:
        print(f"FAIL: Settings test failed: {e}")
        return False

def test_database_connections():
    """Test database connections"""
    print("\nTesting database connections...")
    try:
        from data.db_mysql import db_mysql
        from data.db_duck import db_duck
        from sqlalchemy import text
        
        # Test MySQL connection
        try:
            with db_mysql.engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                print("PASS: MySQL connection successful")
        except Exception as e:
            print(f"FAIL: MySQL connection failed: {e}")
            print("   Make sure MySQL is running and credentials in .env are correct")
            return False
        
        # Test DuckDB connection
        try:
            with db_duck.engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                print("PASS: DuckDB connection successful")
        except Exception as e:
            print(f"FAIL: DuckDB connection failed: {e}")
            return False
        
        return True
    except Exception as e:
        print(f"FAIL: Database connection test failed: {e}")
        return False

def test_portalocker():
    """Test that portalocker is working (Windows compatibility fix)"""
    print("\nTesting portalocker (Windows compatibility)...")
    try:
        import portalocker
        import tempfile
        
        # Create a temporary file and test locking
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            temp_file = f.name
        
        try:
            with open(temp_file, 'w') as f:
                portalocker.lock(f, portalocker.LOCK_EX | portalocker.LOCK_NB)
                print("PASS: File locking works (portalocker)")
                portalocker.unlock(f)
        finally:
            os.unlink(temp_file)
        
        return True
    except Exception as e:
        print(f"FAIL: Portalocker test failed: {e}")
        return False

def main():
    print("=" * 60)
    print("Job Application Engine - Setup Verification")
    print("=" * 60)
    
    results = []
    
    # Run tests
    results.append(("Imports", test_imports()))
    results.append(("Settings", test_settings()))
    results.append(("Portalocker", test_portalocker()))
    results.append(("Database Connections", test_database_connections()))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"{test_name}: {status}")
    
    all_passed = all(result[1] for result in results)
    
    print("\n" + "=" * 60)
    if all_passed:
        print("Success: All tests passed! Your setup is ready.")
        print("\nNext steps:")
        print("1. Run: python scripts/init_db.py (if not done yet)")
        print("2. Test: python scripts/main.py --dry-run")
    else:
        print("Warning: Some tests failed. Please fix the issues above.")
        print("\nCommon fixes:")
        print("- Update DB_PASSWORD in .env file")
        print("- Make sure MySQL server is running")
        print("- Run: CREATE DATABASE test; in MySQL")
        print("- Run: pip install -r requirements.txt")
    print("=" * 60)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
