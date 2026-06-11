import sqlite3
import argparse
import sys
import os

try:
    from werkzeug.security import generate_password_hash
except ImportError:
    print("Error: werkzeug is not installed. Please run: pip install werkzeug")
    sys.exit(1)

def add_user(username, password, role="admin"):
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "inventory.db")
    
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}.")
        print("Make sure you run this script from the same directory as inventory.db or start the server first.")
        sys.exit(1)

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if user already exists
        cursor.execute("SELECT username FROM web_users WHERE username = ?", (username,))
        if cursor.fetchone():
            print(f"Error: User '{username}' already exists.")
            sys.exit(1)
            
        hashed_pw = generate_password_hash(password)
        cursor.execute("INSERT INTO web_users (username, password_hash, role) VALUES (?, ?, ?)",
                       (username, hashed_pw, role))
        conn.commit()
        print(f"Success: Added user '{username}' with role '{role}'.")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add a new Web Dashboard user to the database.")
    parser.add_argument("username", help="The username for the new account")
    parser.add_argument("password", help="The password for the new account")
    parser.add_argument("--role", default="admin", help="The role of the user (default: admin)")
    
    args = parser.parse_args()
    add_user(args.username, args.password, args.role)
