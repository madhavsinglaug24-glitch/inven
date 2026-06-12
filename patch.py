import re

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_routes = """
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
"""

target = '@app.route("/api/history", methods=["GET"])'
if target in content:
    content = content.replace(target, new_routes + '\n' + target)
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched app.py successfully")
else:
    print("Target not found in app.py")
