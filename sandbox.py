from datetime import datetime, timezone
import getpass
import socket
import sys
import psycopg2
from psycopg2 import sql

host = "aws-0-ap-southeast-1.pooler.supabase.com"
port = 6543
db_name = "postgres"
username = "postgres.qltqswnznlpfamrlctoz"
pwd = "Josie4lifetestDB"

DB_URL = f"postgresql://{username}:{pwd}@{host}:{port}/{db_name}"

def learnDateTime():
    ts = datetime.now(timezone.utc)

    print(f"UtcNow: {ts}")
    print(type(ts))

    id = 18
    print(type(id))
    id2: str = str(id)
    print(type(id2))

def getusermeta():
    username = getpass.getuser()
    hostname = socket.gethostname()

    print(f"Username: {username}")
    print(f"Hostname: {hostname}")

def test_lists():
    #perms = ["admin", "user", "read", "planner"]
    perms = []

    if not "admin" in perms and not "user" in perms:
        print("you do not have access")

def test_set():
    dict1 = {"name": "jon", "age": 38}

    dict1["height"] = 171
    print(dict1)


def test_database_connection():
    try:
        print("Connecting to PostgreSQL database...")
        # requires SSL connections
        conn = psycopg2.connect(
            dbname=db_name,
            user=username, 
            password=pwd, 
            host=host,
            port=port,
            sslmode="require"
            )
        
        conn.autocommit = True  # Automatically commit transactions
        cursor = conn.cursor()
        print("Connected successfully!\n")

        # 1. Create Table
        print("Creating table 'test_items'...")
        create_table_query = """
        CREATE TABLE IF NOT EXISTS test_items (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            category VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        cursor.execute(create_table_query)
        print("Table 'test_items' ready.")

        # 2. Insert Sample Records
        print("\nInserting sample records...")
        sample_data = [
            ("Alpha Item", "Hardware"),
            ("Beta Item", "Software"),
            ("Gamma Item", "Services")
        ]
        
        insert_query = """
        INSERT INTO test_items (name, category)
        VALUES (%s, %s);
        """
        cursor.executemany(insert_query, sample_data)
        print(f"Inserted {len(sample_data)} rows successfully.")

        # 3. Query the Table
        print("\nQuerying table records...")
        select_query = "SELECT id, name, category, created_at FROM test_items ORDER BY id DESC LIMIT 5;"
        cursor.execute(select_query)
        
        rows = cursor.fetchall()
        print("\n--- QUERY RESULTS ---")
        for row in rows:
            print(f"ID: {row[0]} | Name: {row[1]} | Category: {row[2]} | Created At: {row[3]}")
        print("---------------------")

        # Clean up
        cursor.close()
        conn.close()
        print("\nConnection closed safely. Test completed successfully!")

    except Exception as error:
        print(f"\n[ERROR] Database connection or execution failed: {error}")
        sys.exit(1)




if __name__ == "__main__":
    test_database_connection()
