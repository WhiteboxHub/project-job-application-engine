"""
Execute SQL migration script on MySQL database
"""
import mysql.connector
from mysql.connector import Error
import os

def run_migration():
    sql_file = "db/migration_add_automation_tables.sql"
    
    try:
        # Connect to MySQL
        connection = mysql.connector.connect(
            host='127.0.0.1',
            port=3306,
            user='root',
            password='M@hi14119866',
            database='new_db'
        )
        
        if connection.is_connected():
            cursor = connection.cursor()
            
            # Read SQL file
            with open(sql_file, 'r', encoding='utf-8') as f:
                sql_script = f.read()
            
            # Split by semicolons and execute each statement
            statements = sql_script.split(';')
            
            print("=" * 80)
            print("🚀 Starting Database Migration")
            print("=" * 80)
            print()
            
            for i, statement in enumerate(statements):
                statement = statement.strip()
                if statement and not statement.startswith('--'):
                    try:
                        # Execute statement
                        cursor.execute(statement)
                        
                        # Fetch results if any (for SELECT statements)
                        if cursor.description:
                            results = cursor.fetchall()
                            if results:
                                for row in results:
                                    print(' | '.join(str(col) for col in row))
                        
                    except Error as e:
                        # Skip errors for statements like SET, PREPARE, etc.
                        if "already exists" not in str(e):
                            print(f"⚠️  Statement {i+1}: {e}")
            
            # Commit changes
            connection.commit()
            
            print()
            print("=" * 80)
            print("✅ Migration completed successfully!")
            print("=" * 80)
            
            cursor.close()
            connection.close()
            
    except Error as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_migration()
