"""
Inven — Inventory & Ledger Web Dashboard
========================================
Flask backend serving the React dashboard for inventory and ledger management.

Environment variables (see .env.example):
    DASHBOARD_PASSWORD   – Legacy dashboard password login
    ADMIN_USERNAME       – Default web user seeded on first run
    FLASK_SECRET_KEY     – JWT signing secret for web sessions
    OPENAI_API_KEY       – Optional, for receipt scanning via OpenRouter
"""

import os
import json
import uuid
import logging
from datetime import datetime, timezone, timedelta

import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from flask_socketio import SocketIO
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix

from ledger_calculations import (
    TRANSACTIONS_WITH_BALANCE_SQL,
    balances_match_summary,
    count_ledger_rows,
    fetch_month_stats,
    fetch_summary,
    latest_balances_by_account,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
load_dotenv()

# Serve React frontend from the dist folder
app = Flask(__name__, static_folder="frontend/dist", static_url_path="/")
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
CORS(app)
app.config["SECRET_KEY"] = os.urandom(24)

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "InvenVault2026!")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "Manager")

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SQLite Database Helpers
# ---------------------------------------------------------------------------
import sqlite3

def get_db_connection():
    """Create a connection to the SQLite database with row factory enabled."""
    conn = sqlite3.connect("inventory.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Ensure all required database tables exist."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Users Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                phone_number TEXT PRIMARY KEY,
                name TEXT,
                role TEXT
            )
        """)

        # Inventory Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                item_id TEXT PRIMARY KEY,
                item_name TEXT,
                current_stock INTEGER,
                min_stock INTEGER,
                purchase_price REAL,
                supplier_id TEXT
            )
        """)

        # Suppliers Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS suppliers (
                supplier_id TEXT PRIMARY KEY,
                name TEXT,
                contact_number TEXT
            )
        """)

        # Approvals Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS approvals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT,
                worker_number TEXT,
                item_id TEXT,
                action TEXT,
                quantity INTEGER,
                status TEXT
            )
        """)

        # History Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                item_id TEXT,
                item_name TEXT,
                action TEXT,
                quantity INTEGER,
                user_phone TEXT,
                previous_stock INTEGER,
                new_stock INTEGER,
                contact_type TEXT,
                contact_name TEXT,
                comment TEXT,
                txn_id TEXT,
                bill_no TEXT
            )
        """)

        # Ledger Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                type TEXT,
                amount REAL,
                name TEXT,
                comment TEXT,
                logged_by TEXT,
                txn_id TEXT
            )
        """)

        # User Preferences Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_prefs (
                phone_number TEXT PRIMARY KEY,
                language TEXT
            )
        """)
        
        # Web Dashboard Users Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS web_users (
                username TEXT PRIMARY KEY,
                password_hash TEXT,
                role TEXT
            )
        """)
        
        # Consumers Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS consumers (
                consumer_id TEXT PRIMARY KEY,
                name TEXT,
                contact_number TEXT
            )
        """)

        # Merchants Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS merchants (
                merchant_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
        """)
        
        conn.execute('CREATE INDEX IF NOT EXISTS idx_history_timestamp ON history (timestamp DESC)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_ledger_timestamp ON ledger (timestamp DESC)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_inventory_item_id ON inventory (item_id)')
        conn.commit()

        # Seed default admin if empty
        row = cursor.execute("SELECT COUNT(*) FROM web_users").fetchone()
        if row and row[0] == 0:
            import os
            from werkzeug.security import generate_password_hash
            default_user = os.environ.get("ADMIN_USERNAME", "Manager")
            default_pass = os.environ.get("DASHBOARD_PASSWORD", "InvenVault2026!")
            cursor.execute("INSERT INTO web_users (username, password_hash, role) VALUES (?, ?, ?)",
                           (default_user, generate_password_hash(default_pass), "admin"))
            conn.commit()


        # Database migrations
        try:
            cursor.execute("ALTER TABLE history ADD COLUMN unit_price REAL DEFAULT 0")
            conn.commit()
        except Exception:
            pass
            
        try:
            cursor.execute("ALTER TABLE ledger ADD COLUMN account TEXT DEFAULT 'Cash'")
            conn.commit()
        except Exception:
            pass


# Self-initialize database tables on app load
init_db()


# ---- Inventory ------------------------------------------------------------

def get_all_inventory() -> list[dict]:
    """Return every row from the Inventory tab as a list of dicts."""
    try:
        with get_db_connection() as conn:
            rows = conn.execute("SELECT * FROM inventory").fetchall()
            return [{
                "Item_ID": r["item_id"],
                "Item_Name": r["item_name"],
                "Current_Stock": r["current_stock"],
                "Min_Stock": r["min_stock"],
                "Purchase_Price": r["purchase_price"],
                "Supplier_ID": r["supplier_id"]
            } for r in rows]
    except Exception as e:
        logger.error(f"Error querying all inventory: {e}")
        return []


def get_inventory_item(item_id: str) -> dict | None:
    """Return a single inventory row by Item_ID."""
    try:
        with get_db_connection() as conn:
            row = conn.execute("SELECT * FROM inventory WHERE item_id = ?", (str(item_id).strip(),)).fetchone()
            if row:
                return {
                    "Item_ID": row["item_id"],
                    "Item_Name": row["item_name"],
                    "Current_Stock": row["current_stock"],
                    "Min_Stock": row["min_stock"],
                    "Purchase_Price": row["purchase_price"],
                    "Supplier_ID": row["supplier_id"]
                }
    except Exception as e:
        logger.error(f"Error querying inventory item {item_id}: {e}")
    return None


def update_inventory_stock(item_id: str, new_stock: int):
    """Overwrite Current_Stock for the given Item_ID."""
    try:
        with get_db_connection() as conn:
            conn.execute("UPDATE inventory SET current_stock = ? WHERE item_id = ?", (new_stock, str(item_id).strip()))
            conn.commit()
    except Exception as e:
        logger.error(f"Error updating stock for item {item_id}: {e}")


# ---- Suppliers ------------------------------------------------------------

def get_supplier(supplier_id: str) -> dict | None:
    """Return a Supplier row by Supplier_ID."""
    try:
        with get_db_connection() as conn:
            row = conn.execute("SELECT * FROM suppliers WHERE supplier_id = ?", (str(supplier_id).strip(),)).fetchone()
            if row:
                return {
                    "Supplier_ID": row["supplier_id"],
                    "Name": row["name"],
                    "Contact_Number": row["contact_number"]
                }
    except Exception as e:
        logger.error(f"Error querying supplier {supplier_id}: {e}")
    return None


# ---- History --------------------------------------------------------------

def log_history(item_id: str, item_name: str, action: str, qty: int, editor: str, previous_stock: int, new_stock: int, contact_type: str = "", contact_name: str = "", comment: str = "", txn_id: str = None, bill_no: str = ""):
    """Log an inventory change to the History tab."""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not txn_id:
            txn_id = f"TXN-{uuid.uuid4().hex[:6].upper()}"
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO history (timestamp, item_id, item_name, action, quantity, user_phone, previous_stock, new_stock, contact_type, contact_name, comment, txn_id, bill_no) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (timestamp, item_id, item_name, action, qty, str(editor).strip(), previous_stock, new_stock, contact_type, contact_name, comment, txn_id, bill_no)
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to log history: {e}")


# ---------------------------------------------------------------------------
# Web routes
# ---------------------------------------------------------------------------

@app.route("/", methods=["GET"])
def index():
    """Serve the React frontend."""
    if not os.path.exists(app.static_folder):
        return jsonify({"status": "online", "message": "Frontend not built yet. Please run npm run build in frontend directory."}), 200
    
    response = app.send_static_file("index.html")
    # Tell browser to validate the HTML file before using a cached copy
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response

@app.route("/<path:path>")
def serve_static(path):
    """Serve static files or fallback to React router."""
    if not app.static_folder:
        return "Not found", 404
        
    full_path = os.path.join(app.static_folder, path)
    if os.path.exists(full_path) and not os.path.isdir(full_path):
        response = send_from_directory(app.static_folder, path)
        # Aggressively cache static assets (JS, CSS, images) for 1 year
        if path.startswith("assets/") or path.endswith((".js", ".css", ".png", ".svg", ".ico")):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response
        
    # Fallback to index.html for React Router
    response = app.send_static_file("index.html")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response

@app.after_request
def add_cache_headers(response):
    """Ensure API requests are never cached by the browser."""
    if request.path.startswith("/api/") or request.path.startswith("/dashboard/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "-1"
    return response

@app.route("/health", methods=["GET"])
def health():
    """Simple health-check endpoint."""
    return jsonify({"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}), 200


# ---------------------------------------------------------------------------
# Dashboard Web UI & REST APIs
# ---------------------------------------------------------------------------

def check_dashboard_auth():
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return False
        
    token = auth_header.split(" ")[1]
    
    # Backwards compatibility for testing without SSO
    if token.startswith("dash-") or token == "admin":
        return True
        
    try:
        import jwt
        secret = os.environ.get("FLASK_SECRET_KEY", "default-sde-secret-key-123")
        jwt.decode(token, secret, algorithms=["HS256"])
        return True
    except Exception as e:
        logger.error(f"JWT Verification failed: {e}")
        return False


def normalize_amount(raw) -> float:
    """Round monetary values to 2 decimal places."""
    return round(float(raw), 2)


def validate_positive_amount(amount: float) -> str | None:
    """Return an error message if amount is invalid, else None."""
    if amount <= 0:
        return "Amount must be greater than 0"
    return None


@app.route("/api/auth/login", methods=["POST"])
def standard_login():
    import jwt
    from datetime import timedelta
    
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    
    if not username or not password:
        return jsonify({"message": "Username and password required"}), 400
        
    env_user = os.environ.get("ADMIN_USERNAME", "Manager")
    env_pass = os.environ.get("DASHBOARD_PASSWORD", "InvenVault2026!")
    
    role = None
    if username == env_user and password == env_pass:
        role = "admin"
    else:
        with get_db_connection() as conn:
            user = conn.execute("SELECT * FROM web_users WHERE username = ?", (username,)).fetchone()
            
        if not user or not check_password_hash(user["password_hash"], password):
            return jsonify({"message": "Invalid username or password"}), 401
        role = user["role"]
        
    # Create persistent session token (valid for 30 days)
    payload = {
        "username": username,
        "role": role,
        "exp": datetime.utcnow() + timedelta(days=30)
    }
    secret = os.environ.get("FLASK_SECRET_KEY", "default-sde-secret-key-123")
    session_token = jwt.encode(payload, secret, algorithm="HS256")
    
    return jsonify({"token": session_token, "username": username, "role": role}), 200





@app.route("/dashboard/login", methods=["POST"])
def dashboard_login():
    """Authenticate manager password and return a temporary API session token."""
    data = request.get_json() or {}
    password = data.get("password")
    if password == DASHBOARD_PASSWORD:
        token = f"dash-{uuid.uuid4().hex}"
        return jsonify({"token": token}), 200
    return jsonify({"message": "Invalid password"}), 401


@app.route("/api/inventory", methods=["GET"])
def api_inventory():
    """Get all current inventory items."""
    if not check_dashboard_auth():
        return jsonify({"message": "Unauthorized"}), 401
    try:
        return jsonify(get_all_inventory()), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500


@app.route("/api/inventory/<item_id>/stock", methods=["POST"])
def api_update_stock(item_id):
    """Directly override inventory item stock level from the dashboard."""
    if not check_dashboard_auth():
        return jsonify({"message": "Unauthorized"}), 401
    data = request.get_json() or {}
    new_stock = data.get("stock")
    if new_stock is None or not isinstance(new_stock, int) or new_stock < 0:
        return jsonify({"message": "Invalid stock level"}), 400
    try:
        item = get_inventory_item(item_id)
        if not item:
            return jsonify({"message": "Item not found"}), 404
        old_stock = int(item.get("Current_Stock", 0))
        update_inventory_stock(item_id, new_stock)
        log_history(item_id, item["Item_Name"], "Dashboard Edit", abs(new_stock - old_stock), "Dashboard", old_stock, new_stock, comment="Manual edit from dashboard")
        socketio.emit("inventory_updated", {"message": "Item stock updated via API"})
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500


@app.route("/api/ledger", methods=["GET"])
def api_ledger():
    """Retrieve all entries from the ledger journal in descending order."""
    if not check_dashboard_auth():
        return jsonify({"message": "Unauthorized"}), 401
    try:
        with get_db_connection() as conn:
            rows = conn.execute("SELECT * FROM ledger ORDER BY id DESC").fetchall()
            return jsonify([{
                "id": r["id"],
                "Date": r["timestamp"],
                "Type": r["type"],
                "Amount": r["amount"],
                "Name": r["name"],
                "Comment": r["comment"],
                "Logged_By": r["logged_by"],
                "Txn_ID": r["txn_id"]
            } for r in rows]), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500


@app.route("/api/stats", methods=["GET"])
def api_stats():
    """Compute and compile high-level dashboard performance metrics."""
    if not check_dashboard_auth():
        return jsonify({"message": "Unauthorized"}), 401
    try:
        inventory = get_all_inventory()
        low_stock_count = sum(1 for item in inventory if int(item.get("Current_Stock", 0)) < int(item.get("Min_Stock", 0)))
        
        with get_db_connection() as conn:
            current_month_str = datetime.now().strftime("%Y-%m")
            month_in, month_out = fetch_month_stats(conn, current_month_str)
            summary = fetch_summary(conn)
            
        return jsonify({
            "low_stock_count": low_stock_count,
            "cash_in_hand": summary["cash_balance"],
            "month_credit": month_in,
            "month_debit": month_out
        }), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500



@app.route("/api/summary", methods=["GET"])
def api_summary():
    if not check_dashboard_auth():
        return jsonify({"message": "Unauthorized"}), 401
    try:
        start = request.args.get("start") or None
        end = request.args.get("end") or None
        with get_db_connection() as conn:
            return jsonify(fetch_summary(conn, start=start, end=end))
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route("/api/transactions", methods=["GET"])
def get_transactions():
    if not check_dashboard_auth():
        return jsonify({"message": "Unauthorized"}), 401
    try:
        limit = int(request.args.get('limit', 1000))
        with get_db_connection() as conn:
            rows = conn.execute(TRANSACTIONS_WITH_BALANCE_SQL, (limit,)).fetchall()
            
            formatted_txs = []
            for r in rows:
                amt = float(r['amount'])
                if 'OUT' in str(r['type']).upper():
                    debit = amt
                    credit = 0.0
                else:
                    debit = 0.0
                    credit = amt
                    
                formatted_txs.append({
                    'id': r['id'],
                    'txn_id': r['txn_id'] if 'txn_id' in r.keys() else 'N/A',
                    'date': r['timestamp'],
                    'merchant': r['name'] or 'Unknown',
                    'credit': credit,
                    'debit': debit,
                    'balance': r['net_balance'],
                    'acct_balance': r['acct_balance'],
                    'account': r['account'] if 'account' in r.keys() else 'Cash'
                })
            return jsonify(formatted_txs), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route("/api/transactions", methods=["POST"])
def add_transaction():
    if not check_dashboard_auth():
        return jsonify({"message": "Unauthorized"}), 401
    try:
        data = request.json
        amount = normalize_amount(data.get("amount", 0))
        amount_err = validate_positive_amount(amount)
        if amount_err:
            return jsonify({"error": amount_err}), 400
        
        merchant = data.get("merchant", "Manual Entry")
        if not merchant: return jsonify({"error": "Merchant is required"}), 400
        
        description = data.get("description", "")
        comment = description if description else 'Added from Web Dashboard'
        tx_type = data.get("type", "expense") # "income" or "expense"
        tx_date = data.get("date", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        account = data.get("account", "Cash")
        
        if tx_type == "expense":
            ledger_type = 'Cash OUT'
        else:
            ledger_type = 'Cash IN'
        
        with get_db_connection() as conn:
            conn.execute('INSERT INTO ledger (timestamp, type, amount, name, comment, logged_by, account) VALUES (?, ?, ?, ?, ?, ?, ?)',
                         (tx_date, ledger_type, amount, merchant, comment, 'Web User', account))
            conn.commit()
        socketio.emit("inventory_updated", {"message": "Transaction added"})
        return jsonify({"success": True, "message": "Transaction added."}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route("/api/transfer", methods=["POST"])
def add_transfer():
    if not check_dashboard_auth():
        return jsonify({"message": "Unauthorized"}), 401
    try:
        data = request.json
        amount = normalize_amount(data.get("amount", 0))
        amount_err = validate_positive_amount(amount)
        if amount_err:
            return jsonify({"error": amount_err}), 400
        
        direction = data.get("direction") # "cash_to_bank" or "bank_to_cash"
        if direction not in ["cash_to_bank", "bank_to_cash"]: return jsonify({"error": "Invalid direction"}), 400
        
        tx_date = data.get("date", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        comment = data.get("description", "Self Transfer")
        if not comment: comment = "Self Transfer"
        
        with get_db_connection() as conn:
            if direction == "cash_to_bank":
                conn.execute('INSERT INTO ledger (timestamp, type, amount, name, comment, logged_by, account) VALUES (?, ?, ?, ?, ?, ?, ?)',
                             (tx_date, 'Cash OUT', amount, 'Self Transfer', comment, 'Web User', 'Cash'))
                conn.execute('INSERT INTO ledger (timestamp, type, amount, name, comment, logged_by, account) VALUES (?, ?, ?, ?, ?, ?, ?)',
                             (tx_date, 'Cash IN', amount, 'Self Transfer', comment, 'Web User', 'Bank'))
            else:
                conn.execute('INSERT INTO ledger (timestamp, type, amount, name, comment, logged_by, account) VALUES (?, ?, ?, ?, ?, ?, ?)',
                             (tx_date, 'Cash OUT', amount, 'Self Transfer', comment, 'Web User', 'Bank'))
                conn.execute('INSERT INTO ledger (timestamp, type, amount, name, comment, logged_by, account) VALUES (?, ?, ?, ?, ?, ?, ?)',
                             (tx_date, 'Cash IN', amount, 'Self Transfer', comment, 'Web User', 'Cash'))
            conn.commit()
            
        socketio.emit("inventory_updated", {"message": "Transfer added"})
        return jsonify({"success": True, "message": "Transfer completed."}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route("/api/transactions/<id>", methods=["PUT", "DELETE"])
def update_transaction(id):
    if not check_dashboard_auth():
        return jsonify({"message": "Unauthorized"}), 401
    try:
        with get_db_connection() as conn:
            if request.method == "DELETE":
                data = request.get_json(silent=True) or {}
                if not data.get("confirmed"):
                    return jsonify({"error": "Deletion requires explicit confirmation"}), 400
                existing = conn.execute("SELECT id FROM ledger WHERE id = ?", (id,)).fetchone()
                if not existing:
                    return jsonify({"error": "Transaction not found"}), 404
                conn.execute("DELETE FROM ledger WHERE id = ?", (id,))
                conn.commit()
                return jsonify({"success": True}), 200
            elif request.method == "PUT":
                existing = conn.execute("SELECT id FROM ledger WHERE id = ?", (id,)).fetchone()
                if not existing:
                    return jsonify({"error": "Transaction not found"}), 404
                data = request.json
                if 'amount' in data:
                    amount = normalize_amount(data['amount'])
                    amount_err = validate_positive_amount(amount)
                    if amount_err:
                        return jsonify({"error": amount_err}), 400
                    data = {**data, 'amount': amount}
                updates = []
                params = []
                for field in ['amount', 'name', 'comment', 'timestamp', 'account']:
                    if field in data:
                        updates.append(f"{field} = ?")
                        params.append(data[field])
                if not updates:
                    return jsonify({"error": "No updates provided"}), 400
                params.append(id)
                cursor = conn.execute(f"UPDATE ledger SET {', '.join(updates)} WHERE id = ?", params)
                if cursor.rowcount == 0:
                    return jsonify({"error": "Transaction not found"}), 404
                conn.commit()
                return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route("/api/suppliers", methods=["GET", "POST"])
def manage_suppliers():
    if not check_dashboard_auth(): return jsonify({"message": "Unauthorized"}), 401
    try:
        with get_db_connection() as conn:
            if request.method == "GET":
                rows = conn.execute("SELECT * FROM suppliers").fetchall()
                return jsonify([dict(r) for r in rows]), 200
            elif request.method == "POST":
                data = request.json
                name = data.get("name")
                if not name: return jsonify({"error": "Name required"}), 400
                import uuid
                sup_id = str(uuid.uuid4())[:8]
                conn.execute("INSERT INTO suppliers (supplier_id, name) VALUES (?, ?)", (sup_id, name))
                conn.commit()
                return jsonify({"success": True, "supplier_id": sup_id, "name": name}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route("/api/suppliers/<supplier_id>", methods=["DELETE"])
def delete_supplier(supplier_id):
    if not check_dashboard_auth(): return jsonify({"message": "Unauthorized"}), 401
    try:
        with get_db_connection() as conn:
            conn.execute("DELETE FROM suppliers WHERE supplier_id = ?", (supplier_id,))
            conn.commit()
        socketio.emit("inventory_updated", {"message": "Supplier deleted"})
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route("/api/consumers", methods=["GET", "POST"])
def manage_consumers():
    if not check_dashboard_auth(): return jsonify({"message": "Unauthorized"}), 401
    try:
        with get_db_connection() as conn:
            if request.method == "GET":
                rows = conn.execute("SELECT * FROM consumers").fetchall()
                return jsonify([dict(r) for r in rows]), 200
            elif request.method == "POST":
                data = request.json
                name = data.get("name")
                if not name: return jsonify({"error": "Name required"}), 400
                import uuid
                con_id = str(uuid.uuid4())[:8]
                conn.execute("INSERT INTO consumers (consumer_id, name) VALUES (?, ?)", (con_id, name))
                conn.commit()
                return jsonify({"success": True, "consumer_id": con_id, "name": name}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route("/api/consumers/<consumer_id>", methods=["DELETE"])
def delete_consumer(consumer_id):
    if not check_dashboard_auth(): return jsonify({"message": "Unauthorized"}), 401
    try:
        with get_db_connection() as conn:
            conn.execute("DELETE FROM consumers WHERE consumer_id = ?", (consumer_id,))
            conn.commit()
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route("/api/history/<id>", methods=["PUT", "DELETE"])
def update_history(id):
    if not check_dashboard_auth(): return jsonify({"message": "Unauthorized"}), 401
    try:
        with get_db_connection() as conn:
            if request.method == "PUT":
                data = request.json
                updates = []
                params = []
                for field in ['quantity', 'unit_price', 'contact_name', 'comment', 'timestamp']:
                    if field in data:
                        if field in ['quantity', 'unit_price'] and float(data[field]) < 0:
                            return jsonify({"error": f"{field} cannot be negative"}), 400
                        updates.append(f"{field} = ?")
                        params.append(data[field])
                if not updates: return jsonify({"error": "No updates provided"}), 400
                params.append(id)
                conn.execute(f"UPDATE history SET {', '.join(updates)} WHERE id = ?", params)
                conn.commit()
                return jsonify({"success": True}), 200
                
            elif request.method == "DELETE":
                # Get the history row
                row = conn.execute("SELECT * FROM history WHERE id = ?", (id,)).fetchone()
                if not row:
                    return jsonify({"error": "History log not found"}), 404
                
                # Reverse the stock change in inventory
                item_id = row['item_id']
                qty = row['quantity']
                action = row['action']
                
                inventory_item = conn.execute("SELECT current_stock FROM inventory WHERE item_id = ?", (item_id,)).fetchone()
                if inventory_item:
                    current_stock = inventory_item['current_stock']
                    if action == 'RESTOCK':
                        new_stock = current_stock - qty
                    else: # CONSUME
                        new_stock = current_stock + qty
                    
                    # Update inventory
                    conn.execute("UPDATE inventory SET current_stock = ? WHERE item_id = ?", (new_stock, item_id))
                    
                # Delete the history row
                conn.execute("DELETE FROM history WHERE id = ?", (id,))
                conn.commit()
                
            return jsonify({"success": True}), 200
            
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/merchants", methods=["GET", "POST"])
def api_merchants():
    try:
        with get_db_connection() as conn:
            if request.method == "GET":
                rows = conn.execute("SELECT * FROM merchants ORDER BY name ASC").fetchall()
                return jsonify([dict(r) for r in rows]), 200
            elif request.method == "POST":
                data = request.json
                name = data.get("name", "").strip()
                if not name: return jsonify({"error": "Name required"}), 400
                conn.execute("INSERT OR IGNORE INTO merchants (name) VALUES (?)", (name,))
                conn.commit()
                row = conn.execute("SELECT * FROM merchants WHERE name=?", (name,)).fetchone()
                return jsonify(dict(row)), 201
    except Exception as e:
        logger.error(f"Merchants API error: {e}")
        return jsonify({"error": "Database error"}), 500

@app.route("/api/merchants/<merchant_id>", methods=["DELETE"])
def api_delete_merchant(merchant_id):
    try:
        with get_db_connection() as conn:
            conn.execute("DELETE FROM merchants WHERE merchant_id=?", (merchant_id,))
            conn.commit()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"error": "Database error"}), 500

@app.route("/api/history", methods=["GET"])
def get_history():
    if not check_dashboard_auth(): return jsonify({"message": "Unauthorized"}), 401
    try:
        limit = int(request.args.get('limit', 1000))
        with get_db_connection() as conn:
            rows = conn.execute("SELECT * FROM history ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
            return jsonify([dict(r) for r in rows]), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500
@app.route('/api/inventory/<item_id>', methods=['DELETE'])
def delete_inventory_item(item_id):
    if not check_dashboard_auth(): return jsonify({"message": "Unauthorized"}), 401
    try:
        with get_db_connection() as conn:
            conn.execute("DELETE FROM inventory WHERE item_id = ?", (item_id,))
            conn.commit()
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/inventory/add', methods=['POST'])
def add_new_item():
    if not check_dashboard_auth():
        return jsonify({"message": "Unauthorized"}), 401
    try:
        data = request.json
        name = data.get("name")
        item_id = data.get("id")
        min_stock = int(data.get("min_stock", 0))
        cost_price = float(data.get("cost_price", 0))
        
        if not name or not item_id:
            return jsonify({"error": "Item Name and ID required"}), 400
            
        with get_db_connection() as conn:
            existing = conn.execute("SELECT * FROM inventory WHERE item_id = ?", (item_id,)).fetchone()
            if existing:
                return jsonify({"error": "Item ID already exists"}), 400
                
            conn.execute('''INSERT INTO inventory (item_id, item_name, purchase_price, min_stock, current_stock) 
                            VALUES (?, ?, ?, ?, ?)''', 
                         (item_id, name, cost_price, min_stock, 0))
            conn.commit()
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/inventory/update', methods=['POST'])
def inventory_update_react():
    if not check_dashboard_auth():
        return jsonify({"message": "Unauthorized"}), 401
    try:
        data = request.json
        action_type = data.get('type') # 'restock' or 'consume'
        supplier = data.get('supplier', 'Unknown')
        bill_no = data.get('bill_no', '')
        items = data.get('items', [])
        
        # Legacy fallback if they pass single item
        if 'item_id' in data and not items:
            items = [{'item_id': data.get('item_id'), 'qty': data.get('qty', 0), 'price': data.get('price', 0)}]
            
        if not items:
            return jsonify({"error": "No items provided"}), 400
            
        total_price = 0
        names_for_ledger = []
            
        with get_db_connection() as conn:
            for item_req in items:
                item_id = item_req.get('item_id')
                qty = int(item_req.get('qty', 0))
                price = float(item_req.get('price', 0))
                
                if not item_id or qty <= 0: continue
                
                item = conn.execute("SELECT * FROM inventory WHERE item_id = ?", (item_id,)).fetchone()
                if not item: return jsonify({"error": f"Item {item_id} not found"}), 404
                
                old_stock = item['current_stock']
                new_stock = old_stock + qty if action_type == 'restock' else old_stock - qty
                
                if new_stock < 0: return jsonify({"error": f"Insufficient stock for {item['item_name']}"}), 400
                
                # Calculate new average price on restock
                new_avg_price = item['purchase_price']
                if action_type == 'restock' and price > 0 and qty > 0:
                    old_total_value = old_stock * item['purchase_price']
                    new_avg_price = (old_total_value + price) / new_stock

                conn.execute("UPDATE inventory SET current_stock = ?, purchase_price = ? WHERE item_id = ?", (new_stock, new_avg_price, item_id))
                
                # Log history
                unit_price = (price / qty) if qty > 0 else 0
                conn.execute('''INSERT INTO history (timestamp, item_id, item_name, action, quantity, previous_stock, new_stock, contact_type, contact_name, comment, unit_price, bill_no)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                             (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), item_id, item['item_name'], 'RESTOCK' if action_type == 'restock' else 'CONSUME', 
                              qty, old_stock, new_stock, 'Supplier' if action_type == 'restock' else 'System', supplier, 'Web Dashboard', unit_price, bill_no))
                
                total_price += price
                names_for_ledger.append(f"{qty}x {item['item_name']}")
                

            
            conn.commit()
            return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route('/api/scan_receipt', methods=['POST'])
def scan_receipt_api():
    if not check_dashboard_auth():
        return jsonify({"message": "Unauthorized"}), 401
    
    if "receipt" not in request.files:
        return jsonify({"error": "No receipt file provided"}), 400
    
    file = request.files["receipt"]
    try:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return jsonify({"error": "AI scanning offline (API Key missing in .env)"}), 503

        import base64
        import requests as http_requests
        import json
        import re
        file_bytes = file.read()
        b64_img = base64.b64encode(file_bytes).decode('utf-8')
        mime_type = file.content_type or "image/jpeg"

        prompt = (
            "You are analyzing a receipt or invoice image. "
            "Extract the total amount (as a number) and the merchant/store name (as a string). "
            "You MUST respond with ONLY a raw JSON object, no markdown, no explanation. "
            "Example: {\"amount\": 150.00, \"merchant\": \"Big Bazaar\"}"
        )

        payload = {
            "model": "google/gemini-2.0-flash-lite-preview-02-05:free",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64_img}"}}
                    ]
                }
            ],
            "max_tokens": 300,
            "temperature": 0.1
        }
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://sde-dashboard.com",
            "X-Title": "SDE App"
        }
        
        resp = http_requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=30)
        if not resp.ok:
            error_body = resp.text
            try:
                err_json = json.loads(error_body)
                error_msg = err_json.get("error", {}).get("message", error_body)
            except Exception:
                error_msg = error_body
            return jsonify({"error": f"AI Error: {error_msg}"}), 400
        
        resp_json = resp.json()
        msg_content = None
        try:
            msg_content = resp_json["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            pass
        
        if not msg_content:
            return jsonify({"error": "AI returned an empty response. Please try again."}), 400
            
        ai_text = msg_content.strip()
        
        # Strip markdown code fences
        if ai_text.startswith("```json"):
            ai_text = ai_text[7:]
        if ai_text.startswith("```"):
            ai_text = ai_text[3:]
        if ai_text.endswith("```"):
            ai_text = ai_text[:-3]
        ai_text = ai_text.strip()
        
        # Try direct JSON parse first
        try:
            parsed = json.loads(ai_text)
            amount = float(parsed.get("amount", 0))
            merchant = str(parsed.get("merchant", "Unknown"))
            return jsonify({"amount": amount, "merchant": merchant}), 200
        except (json.JSONDecodeError, ValueError):
            pass
        
        # Fallback: find JSON object in the text using regex
        json_match = re.search(r'\{[^{}]*\}', ai_text)
        if json_match:
            try:
                parsed = json.loads(json_match.group())
                amount = float(parsed.get("amount", 0))
                merchant = str(parsed.get("merchant", "Unknown"))
                return jsonify({"amount": amount, "merchant": merchant}), 200
            except (json.JSONDecodeError, ValueError):
                pass
                
        # Fallback 3: Regex extraction for partial/broken text
        amount = 0.0
        merchant = ""
        amt_match = re.search(r'"amount"\s*:\s*([\d\.]+)', ai_text)
        if amt_match:
            try:
                amount = float(amt_match.group(1))
            except:
                pass
        
        merch_match = re.search(r'"merchant"\s*:\s*"([^"]+)"', ai_text)
        if merch_match:
            merchant = merch_match.group(1)
            
        if amount > 0 or merchant:
            return jsonify({"amount": amount, "merchant": merchant or "Unknown"}), 200
        
        return jsonify({"error": f"Could not parse AI response: {ai_text[:200]}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/parse_text', methods=['POST'])
def parse_text_api():
    if not check_dashboard_auth():
        return jsonify({"message": "Unauthorized"}), 401
    
    data = request.get_json()
    if not data or "text" not in data:
        return jsonify({"error": "No text provided"}), 400
        
    text = data["text"]
    available_items = data.get("items", [])
    
    try:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            # Fallback regex parsing if API key is missing
            import re
            amount_match = re.search(r'(?:rs\.?|inr|₹|\$|for|@)\s*([\d\.,]+)', text, re.IGNORECASE)
            qty_match = re.search(r'(\d+)\s*(?:bags|pcs|units|x)?', text, re.IGNORECASE)
            amount = 0.0
            if amount_match:
                try:
                    amount = float(amount_match.group(1).replace(',', ''))
                except:
                    pass
            qty = 1
            if qty_match:
                try:
                    qty = int(qty_match.group(1))
                except:
                    pass
            
            return jsonify({
                "amount": amount,
                "merchant": "",
                "quantity": qty,
                "item_id": available_items[0]['Item_ID'] if available_items else None
            }), 200

        import requests as http_requests
        import json
        import re

        items_str = ", ".join([f"ID {i.get('Item_ID')}: {i.get('Item_Name')}" for i in available_items])
        
        prompt = (
            "You are an assistant that extracts transaction details from a user's natural language input. "
            "Extract the total amount (number), merchant/store name (string), quantity (number), and the best matching item_id from the available items list based on the user's text. "
            "If no amount or merchant is found, leave them blank or 0. If no quantity is found, default to 1. "
            f"Available items: [{items_str}]. "
            "You MUST respond with ONLY a raw JSON object, no markdown, no explanation. "
            "Example: {\"amount\": 150.00, \"merchant\": \"Big Bazaar\", \"quantity\": 10, \"item_id\": 5}"
        )

        payload = {
            "model": "google/gemini-2.0-flash-lite-preview-02-05:free",
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": text}
            ],
            "max_tokens": 300,
            "temperature": 0.1
        }
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://sde-dashboard.com",
            "X-Title": "SDE App"
        }
        
        resp = http_requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=30)
        if not resp.ok:
            return jsonify({"error": "AI Error"}), 400
            
        resp_json = resp.json()
        ai_text = resp_json["choices"][0]["message"]["content"].strip()
        
        if ai_text.startswith("```json"): ai_text = ai_text[7:]
        if ai_text.startswith("```"): ai_text = ai_text[3:]
        if ai_text.endswith("```"): ai_text = ai_text[:-3]
        ai_text = ai_text.strip()
        
        try:
            parsed = json.loads(ai_text)
            return jsonify(parsed), 200
        except:
            json_match = re.search(r'\{[^{}]*\}', ai_text)
            if json_match:
                return jsonify(json.loads(json_match.group())), 200
                
        return jsonify({"error": "Could not parse AI response"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/ledger/integrity", methods=["GET"])
def ledger_integrity():
    """Verify summary totals match running ledger balances."""
    if not check_dashboard_auth():
        return jsonify({"message": "Unauthorized"}), 401
    with get_db_connection() as conn:
        summary = fetch_summary(conn)
        latest = latest_balances_by_account(conn)
        ok = balances_match_summary(conn)
    return jsonify({"ok": ok, "summary": summary, "latest_balances": latest}), 200


@app.route("/api/backup", methods=["GET"])
def api_backup():
    """Securely download a backup of the inventory.db SQL file."""
    if not check_dashboard_auth():
        return jsonify({"message": "Unauthorized"}), 401
    try:
        import os
        db_path = os.path.abspath("inventory.db")
        if os.path.exists(db_path):
            from flask import send_file
            return send_file(db_path, as_attachment=True, download_name="inventory_backup.db")
        else:
            return jsonify({"message": "Database file not found"}), 404
    except Exception as e:
        return jsonify({"message": str(e)}), 500


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
