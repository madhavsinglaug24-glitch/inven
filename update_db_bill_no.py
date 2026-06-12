import sqlite3

def add_bill_no_column():
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute("ALTER TABLE history ADD COLUMN bill_no TEXT")
        conn.commit()
        print("Successfully added 'bill_no' column to 'history' table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("'bill_no' column already exists.")
        else:
            print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    add_bill_no_column()
