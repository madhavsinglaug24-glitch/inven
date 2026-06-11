import sys

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

target1 = 'conn.close()\n    return jsonify({"message": "Item added successfully", "item_id": item_id}), 201'
replacement1 = 'conn.close()\n    socketio.emit("inventory_updated", {"message": "New item added"})\n    return jsonify({"message": "Item added successfully", "item_id": item_id}), 201'
content = content.replace(target1, replacement1)

target2 = 'conn.commit()\n        conn.close()\n        return jsonify({"message": "Item updated successfully"}), 200'
replacement2 = 'conn.commit()\n        conn.close()\n        socketio.emit("inventory_updated", {"message": "Item updated"})\n        return jsonify({"message": "Item updated successfully"}), 200'
content = content.replace(target2, replacement2)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
