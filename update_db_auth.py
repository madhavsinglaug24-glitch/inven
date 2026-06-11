import sys

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add imports
if 'from werkzeug.security import generate_password_hash, check_password_hash' not in content:
    content = content.replace('from flask_socketio import SocketIO', 'from flask_socketio import SocketIO\nfrom werkzeug.security import generate_password_hash, check_password_hash')

# Update init_db
new_table_str = '''
        # Web Dashboard Users Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS web_users (
                username TEXT PRIMARY KEY,
                password_hash TEXT,
                role TEXT
            )
        """)
        conn.commit()

        # Seed default admin if empty
        row = cursor.execute("SELECT COUNT(*) FROM web_users").fetchone()
        if row and row[0] == 0:
            import os
            from werkzeug.security import generate_password_hash
            default_user = os.environ.get("ADMIN_USERNAME", "admin")
            default_pass = os.environ.get("DASHBOARD_PASSWORD", "admin123")
            cursor.execute("INSERT INTO web_users (username, password_hash, role) VALUES (?, ?, ?)",
                           (default_user, generate_password_hash(default_pass), "admin"))
            conn.commit()
'''

# Replace conn.commit() at the end of init_db
old_commit_str = '''
            CREATE TABLE IF NOT EXISTS user_prefs (
                phone_number TEXT PRIMARY KEY,
                language TEXT
            )
        """)
        conn.commit()'''

if 'CREATE TABLE IF NOT EXISTS web_users' not in content:
    content = content.replace(old_commit_str, old_commit_str.replace('conn.commit()', new_table_str))

# Replace standard_login
import re
login_func_pattern = re.compile(r'@app\.route\("/api/auth/login", methods=\["POST"\]\)\ndef standard_login\(\):.*?return jsonify\({"token": session_token, "username": username}\), 200', re.DOTALL)

new_login_func = '''@app.route("/api/auth/login", methods=["POST"])
def standard_login():
    import jwt
    from datetime import datetime, timedelta
    
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    
    if not username or not password:
        return jsonify({"message": "Username and password required"}), 400
        
    with get_db_connection() as conn:
        user = conn.execute("SELECT * FROM web_users WHERE username = ?".replace("'", ""), (username,)).fetchone()
        
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"message": "Invalid username or password"}), 401
        
    # Create persistent session token (valid for 30 days)
    payload = {
        "username": username,
        "role": user["role"],
        "exp": datetime.utcnow() + timedelta(days=30)
    }
    secret = os.environ.get("FLASK_SECRET_KEY", "default-sde-secret-key-123")
    session_token = jwt.encode(payload, secret, algorithm="HS256")
    
    return jsonify({"token": session_token, "username": username, "role": user["role"]}), 200'''

content = login_func_pattern.sub(new_login_func, content)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
