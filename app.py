"""
WhatsApp Inventory Management Chatbot
======================================
Flask backend that integrates the Meta WhatsApp Cloud API with Google Sheets
to provide role-based inventory management through WhatsApp messages.

Environment variables required (see SETUP_GUIDE.md):
    WHATSAPP_TOKEN          – Permanent / temporary access token from Meta
    WHATSAPP_PHONE_ID       – Phone-number ID tied to the WhatsApp Business account
    VERIFY_TOKEN            – Arbitrary string used during webhook verification
    GOOGLE_SHEET_ID         – The ID portion of the Google Sheets URL
    GOOGLE_CREDENTIALS_FILE – Path to the service-account JSON key (default: credentials.json)
"""

import os
import json
import uuid
import logging
from datetime import datetime, timezone

import gspread
import requests
from flask import Flask, request, jsonify
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.urandom(24)

WHATSAPP_TOKEN = os.environ["WHATSAPP_TOKEN"]
WHATSAPP_PHONE_ID = os.environ["WHATSAPP_PHONE_ID"]
VERIFY_TOKEN = os.environ["VERIFY_TOKEN"]
GOOGLE_SHEET_ID = os.environ["GOOGLE_SHEET_ID"]
GOOGLE_CREDENTIALS_FILE = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json")

WHATSAPP_API_URL = (
    f"https://graph.facebook.com/v21.0/{WHATSAPP_PHONE_ID}/messages"
)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Google Sheets helpers
# ---------------------------------------------------------------------------
SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

_gsheet_client = None


def _get_sheet():
    """Return an authorised gspread Spreadsheet object (cached)."""
    global _gsheet_client
    if _gsheet_client is None:
        json_creds = os.environ.get("GOOGLE_CREDENTIALS_JSON")
        if json_creds:
            import json
            creds_dict = json.loads(json_creds)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPES)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name(
                GOOGLE_CREDENTIALS_FILE, SCOPES
            )
        client = gspread.authorize(creds)
        _gsheet_client = client.open_by_key(GOOGLE_SHEET_ID)
    return _gsheet_client


def _worksheet(name: str):
    """Get a worksheet by tab name."""
    return _get_sheet().worksheet(name)


# ---- Users ----------------------------------------------------------------

def get_user(phone: str) -> dict | None:
    """Look up a user by phone number.  Returns dict with keys
    Phone_Number, Name, Role or None."""
    ws = _worksheet("Users")
    records = ws.get_all_records()
    for row in records:
        # Normalise numbers: strip leading "+" and whitespace
        sheet_phone = str(row.get("Phone_Number", "")).strip().lstrip("+")
        if sheet_phone == phone.strip().lstrip("+"):
            return row
    return None


def get_manager_phone() -> str | None:
    """Return the first Manager phone number found in the Users sheet."""
    ws = _worksheet("Users")
    records = ws.get_all_records()
    for row in records:
        if str(row.get("Role", "")).strip().lower() == "manager":
            return str(row["Phone_Number"]).strip().lstrip("+")
    return None


# ---- Inventory ------------------------------------------------------------

def get_all_inventory() -> list[dict]:
    """Return every row from the Inventory tab as a list of dicts."""
    ws = _worksheet("Inventory")
    return ws.get_all_records()


def get_inventory_item(item_id: str) -> dict | None:
    """Return a single inventory row by Item_ID."""
    for item in get_all_inventory():
        if str(item.get("Item_ID", "")).strip() == str(item_id).strip():
            return item
    return None


def update_inventory_stock(item_id: str, new_stock: int):
    """Overwrite Current_Stock for the given Item_ID."""
    ws = _worksheet("Inventory")
    records = ws.get_all_records()
    for idx, row in enumerate(records, start=2):  # row 1 = header
        if str(row.get("Item_ID", "")).strip() == str(item_id).strip():
            # Column index for Current_Stock (1-indexed)
            headers = ws.row_values(1)
            col = headers.index("Current_Stock") + 1
            ws.update_cell(idx, col, new_stock)
            return


# ---- Suppliers ------------------------------------------------------------

def get_supplier(supplier_id: str) -> dict | None:
    """Return a Supplier row by Supplier_ID."""
    ws = _worksheet("Suppliers")
    for row in ws.get_all_records():
        if str(row.get("Supplier_ID", "")).strip() == str(supplier_id).strip():
            return row
    return None


# ---- Approvals ------------------------------------------------------------

def create_approval(worker_phone: str, item_id: str, action: str, qty: int) -> str:
    """Insert a new row in the Approvals sheet and return the Request_ID."""
    ws = _worksheet("Approvals")
    request_id = f"REQ-{uuid.uuid4().hex[:8].upper()}"
    ws.append_row([request_id, worker_phone, item_id, action, qty, "Pending"])
    return request_id


def get_approval(request_id: str) -> dict | None:
    """Return an Approvals row by Request_ID."""
    ws = _worksheet("Approvals")
    for row in ws.get_all_records():
        if str(row.get("Request_ID", "")).strip() == request_id.strip():
            return row
    return None


def update_approval_status(request_id: str, new_status: str):
    """Set the Status column for a given Request_ID."""
    ws = _worksheet("Approvals")
    records = ws.get_all_records()
    headers = ws.row_values(1)
    col = headers.index("Status") + 1
    for idx, row in enumerate(records, start=2):
        if str(row.get("Request_ID", "")).strip() == request_id.strip():
            ws.update_cell(idx, col, new_status)
            return

# ---- History --------------------------------------------------------------

def log_history(item_id: str, item_name: str, action: str, qty: int, editor_phone: str, previous_stock: int, new_stock: int):
    """Log an inventory change to the History tab."""
    try:
        ws = _worksheet("History")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ws.append_row([timestamp, item_id, item_name, action, qty, editor_phone, previous_stock, new_stock])
    except Exception as e:
        logger.error(f"Failed to log history: {e}")

def get_recent_history(limit=5) -> list[dict]:
    """Get the most recent history records."""
    try:
        ws = _worksheet("History")
        records = ws.get_all_records()
        return list(reversed(records))[:limit]
    except Exception:
        return []

# ---------------------------------------------------------------------------
# WhatsApp message-sending helpers
# ---------------------------------------------------------------------------

def _wa_headers() -> dict:
    return {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }


def send_text(to: str, body: str):
    """Send a plain-text WhatsApp message."""
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }
    resp = requests.post(WHATSAPP_API_URL, headers=_wa_headers(), json=payload, timeout=30)
    logger.info("send_text → %s | status=%s", to, resp.status_code)
    return resp.json()


def send_list_message(to: str, header: str, body: str, button_text: str, sections: list):
    """Send a WhatsApp Interactive List message.

    `sections` example::
        [
            {
                "title": "Inventory",
                "rows": [
                    {"id": "item_1", "title": "Widget", "description": "Stock: 50"},
                ]
            }
        ]
    """
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": header},
            "body": {"text": body},
            "action": {
                "button": button_text,
                "sections": sections,
            },
        },
    }
    resp = requests.post(WHATSAPP_API_URL, headers=_wa_headers(), json=payload, timeout=30)
    logger.info("send_list → %s | status=%s", to, resp.status_code)
    return resp.json()


def send_button_message(to: str, body: str, buttons: list):
    """Send an Interactive Reply-Button message.

    `buttons` example::
        [
            {"id": "approve_REQ-ABC", "title": "✅ Approve"},
            {"id": "reject_REQ-ABC",  "title": "❌ Reject"},
        ]
    """
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": b["id"], "title": b["title"]}}
                    for b in buttons
                ]
            },
        },
    }
    resp = requests.post(WHATSAPP_API_URL, headers=_wa_headers(), json=payload, timeout=30)
    logger.info("send_button → %s | status=%s", to, resp.status_code)
    return resp.json()


# ---------------------------------------------------------------------------
# Core conversation-state tracker (in-memory, keyed by phone number)
# ---------------------------------------------------------------------------
# Tracks multi-step flows like "add 10 of item X".
# Structure: { phone: { "state": str, ... extra context } }
user_sessions: dict[str, dict] = {}


def reset_session(phone: str):
    user_sessions.pop(phone, None)


# ---------------------------------------------------------------------------
# Incoming message routing
# ---------------------------------------------------------------------------

def handle_message(phone: str, text: str):
    """Route a plain-text message based on the sender's role."""
    user = get_user(phone)
    if user is None:
        send_text(phone, "⛔ You are not registered in the system. Please contact the Manager.")
        return

    role = str(user.get("Role", "")).strip().lower()
    name = user.get("Name", "User")
    text_lower = text.strip().lower()

    # Greetings / main menu
    if text_lower in ("hi", "hello", "hey", "menu", "start"):
        _send_main_menu(phone, role, name)
        return

    # Check for active multi-step session
    session = user_sessions.get(phone)

    if session:
        _handle_session(phone, role, text, session)
        return

    # Quick commands
    if text_lower in ("view", "inventory", "stock", "list"):
        _send_inventory_list(phone, role)
        return

    if text_lower in ("add", "deduct") and role == "worker":
        user_sessions[phone] = {"state": "awaiting_item_id", "action": text_lower.capitalize()}
        send_text(phone, f"📝 *{text_lower.capitalize()} Stock*\n\nPlease enter the *Item ID*:")
        return

    if text_lower in ("add", "deduct") and role == "manager":
        user_sessions[phone] = {"state": "awaiting_item_id", "action": text_lower.capitalize()}
        send_text(phone, f"📝 *{text_lower.capitalize()} Stock*\n\nPlease enter the *Item ID*:")
        return

    if text_lower == "pending" and role == "manager":
        _send_pending_approvals(phone)
        return

    # Fallback
    send_text(
        phone,
        "🤖 I didn't understand that.\n\n"
        "Type *menu* to see available options.",
    )


def _send_main_menu(phone: str, role: str, name: str):
    """Present the main menu as a List message."""
    rows = [
        {"id": "cmd_view", "title": "📦 View Inventory", "description": "See current stock levels"},
        {"id": "cmd_search", "title": "🔍 Search Item", "description": "Check stock for one item"},
        {"id": "cmd_add", "title": "➕ Add Stock", "description": "Request to add stock"},
        {"id": "cmd_deduct", "title": "➖ Deduct Stock", "description": "Request to deduct stock"},
    ]
    rows.append(
        {"id": "cmd_more", "title": "⚙️ More Options...", "description": "View advanced commands"}
    )

    send_list_message(
        to=phone,
        header=f"Welcome, {name}!",
        body=f"You are logged in as *{role.capitalize()}*.\nSelect an option below.",
        button_text="Menu",
        sections=[{"title": "Options", "rows": rows}],
    )

def _send_more_menu(phone: str, role: str):
    """Present advanced options in a secondary menu."""
    rows = []
    if role == "manager":
        rows.append({"id": "cmd_pending", "title": "🕐 Pending Approvals", "description": "Review worker requests"})
        rows.append({"id": "cmd_history", "title": "🕒 Recent History", "description": "View recent edits"})
        rows.append({"id": "cmd_order", "title": "🛒 Order from Supplier", "description": "Message supplier to order stock"})
        rows.append({"id": "cmd_add_dealer", "title": "➕ Add Dealer", "description": "Register a new supplier"})
    
    rows.append({"id": "cmd_new_item", "title": "➕ Add New Item", "description": "Create a new inventory item"})

    send_list_message(
        to=phone,
        header="⚙️ More Options",
        body="Select an advanced command below.",
        button_text="Options",
        sections=[{"title": "More", "rows": rows}],
    )


def _send_inventory_list(phone: str, role: str):
    """Send inventory as a WhatsApp list.  Workers don't see prices."""
    items = get_all_inventory()
    if not items:
        send_text(phone, "📭 The inventory is empty.")
        return

    rows = []
    total_value = 0
    total_items_with_price = 0
    sum_purchase_price = 0

    for item in items:
        stock = int(item.get("Current_Stock", 0))
        price = item.get("Purchase_Price")
        
        desc = f"Stock: {stock}"
        if role == "manager":
            if price and str(price).isdigit():
                p = int(price)
                desc += f" | Price: ₹{p}"
                total_value += (stock * p)
                sum_purchase_price += p
                total_items_with_price += 1
            else:
                desc += " | Price: N/A"

        rows.append({
            "id": f"inv_{item['Item_ID']}",
            "title": str(item["Item_Name"])[:24],
            "description": desc[:72],
        })

    body_text = "Here is the current stock."
    if role == "manager":
        avg_price = (sum_purchase_price / total_items_with_price) if total_items_with_price > 0 else 0
        body_text = (
            f"Tap an item to view details.\n\n"
            f"📊 *Summary*\n"
            f"Avg Price: ₹{avg_price:.2f}\n"
            f"Total Value: ₹{total_value}"
        )

    send_list_message(
        to=phone,
        header="📦 Inventory",
        body=body_text,
        button_text="View Items",
        sections=[{"title": "Items", "rows": rows[:10]}], # Max 10 items for list message
    )


def _send_pending_approvals(phone: str):
    """Show all Pending approval requests to the Manager."""
    ws = _worksheet("Approvals")
    records = ws.get_all_records()
    pending = [r for r in records if str(r.get("Status", "")).strip().lower() == "pending"]

    if not pending:
        send_text(phone, "✅ No pending approval requests.")
        return

    for req in pending:
        item = get_inventory_item(req["Item_ID"])
        item_name = item["Item_Name"] if item else req["Item_ID"]
        body = (
            f"📋 *Request {req['Request_ID']}*\n"
            f"Worker: {req['Worker_Number']}\n"
            f"Item: {item_name} ({req['Item_ID']})\n"
            f"Action: {req['Action']} {req['Quantity']} units"
        )
        send_button_message(
            to=phone,
            body=body,
            buttons=[
                {"id": f"approve_{req['Request_ID']}", "title": "✅ Approve"},
                {"id": f"reject_{req['Request_ID']}", "title": "❌ Reject"},
            ],
        )


# ---------------------------------------------------------------------------
# Multi-step session handler (Add / Deduct flow)
# ---------------------------------------------------------------------------

def _handle_session(phone: str, role: str, text: str, session: dict):
    """Walk the user through Add / Deduct steps."""
    state = session.get("state")
    action = session.get("action", "Add")

    if text.strip().lower() in ("cancel", "exit", "quit"):
        reset_session(phone)
        send_text(phone, "❌ Operation cancelled.  Type *menu* to start over.")
        return

    # Step: Add New Item
    if state == "awaiting_new_item_name":
        session["new_item_name"] = text.strip()
        session["state"] = "awaiting_new_item_price"
        send_text(phone, f"➕ *Add New Item*\n\nName: {session['new_item_name']}\n\nWhat is the *Purchase Price* (e.g. 500)?")
        return

    if state == "awaiting_new_item_price":
        if not text.strip().isdigit():
            send_text(phone, "⚠️ Please enter a valid number for price. Try again or type *cancel*.")
            return
        session["new_item_price"] = int(text.strip())
        session["state"] = "awaiting_new_item_min_stock"
        send_text(phone, "What is the *Minimum Stock Alert Level* (e.g. 10)?")
        return

    if state == "awaiting_new_item_min_stock":
        if not text.strip().isdigit():
            send_text(phone, "⚠️ Please enter a valid number. Try again or type *cancel*.")
            return
        session["new_item_min_stock"] = int(text.strip())
        session["state"] = "awaiting_new_item_initial_stock"
        send_text(phone, "What is the *Initial Stock Quantity* (e.g. 0)?")
        return

    if state == "awaiting_new_item_initial_stock":
        if not text.strip().isdigit():
            send_text(phone, "⚠️ Please enter a valid number. Try again or type *cancel*.")
            return
        session["new_item_initial_stock"] = int(text.strip())
        session["state"] = "awaiting_new_item_supplier"
        
        # Send supplier selection
        ws = _worksheet("Suppliers")
        records = ws.get_all_records()
        rows = [{"id": "sel_sup_NONE", "title": "None", "description": "No supplier"}]
        for sup in records[:9]:
            rows.append({
                "id": f"sel_sup_{sup['Supplier_ID']}",
                "title": str(sup["Name"])[:24],
                "description": str(sup["Supplier_ID"])[:72]
            })
        
        send_list_message(
            to=phone,
            header="➕ Add New Item",
            body="Select the Supplier for this item:",
            button_text="Select Supplier",
            sections=[{"title": "Suppliers", "rows": rows}]
        )
        return

    # Step: Add Dealer Name
    if state == "awaiting_dealer_name":
        session["dealer_name"] = text.strip()
        session["state"] = "awaiting_dealer_phone"
        send_text(phone, f"➕ *Add Dealer*\n\nName: {text.strip()}\n\nPlease enter their *Phone Number* (with country code, no + or spaces, e.g. 919876543210):")
        return

    # Step: Add Dealer Phone
    if state == "awaiting_dealer_phone":
        dealer_phone = text.strip()
        if not dealer_phone.isdigit():
            send_text(phone, "⚠️ Phone number must contain only digits. Try again or type *cancel*.")
            return
        dealer_name = session["dealer_name"]
        ws = _worksheet("Suppliers")
        records = ws.get_all_records()
        new_id = f"SUP-{len(records) + 1}"
        ws.append_row([new_id, dealer_name, dealer_phone])
        send_text(phone, f"✅ Dealer added successfully!\n\nName: {dealer_name}\nPhone: {dealer_phone}\nID: {new_id}")
        reset_session(phone)
        return

    # Step: Action Search Term (Add / Deduct / Order)
    if state == "awaiting_action_search_term":
        term = text.strip().lower()
        items = get_all_inventory()
        matches = []
        if term == "all":
            matches = items
        else:
            for it in items:
                if term in str(it.get("Item_ID", "")).lower() or term in str(it.get("Item_Name", "")).lower():
                    matches.append(it)
        
        if not matches:
            send_text(phone, "⚠️ No items found matching your search. Try again or type *cancel*.")
            return

        rows = []
        for item in matches[:10]:
            rows.append({
                "id": f"sel_item_{item['Item_ID']}",
                "title": str(item["Item_Name"])[:24],
                "description": f"ID: {item['Item_ID']} | Stock: {item['Current_Stock']}"
            })
        
        send_list_message(
            to=phone,
            header=f"🔍 Search: {term}",
            body=f"Select the item to {action.lower()}:",
            button_text="Select Item",
            sections=[{"title": "Matches", "rows": rows}],
        )
        return

    # Step: Order Item - Prompt
    if state == "awaiting_order_prompt":
        item_name = session["item_name"]
        supplier_name = session["supplier_name"]
        supplier_number = session["supplier_number"]
        custom_msg = text.strip()
        
        wa_link = f"https://wa.me/{supplier_number}?text={requests.utils.quote(custom_msg)}"
        
        send_text(
            phone,
            f"✅ *Message ready!*\n\n"
            f"To: {supplier_name}\n"
            f"Item: {item_name}\n\n"
            f"📲 Tap below to send your message via WhatsApp:\n{wa_link}"
        )
        reset_session(phone)
        return

    # Step: Search Item
    if state == "awaiting_search_term":
        term = text.strip().lower()
        items = get_all_inventory()
        matches = []
        for it in items:
            if term in str(it.get("Item_ID", "")).lower() or term in str(it.get("Item_Name", "")).lower():
                matches.append(it)
        
        if not matches:
            send_text(phone, "⚠️ No items found matching your search. Try again or type *cancel*.")
            return
            
        if len(matches) == 1:
            item = matches[0]
            detail = (
                f"📦 *{item['Item_Name']}*\n\n"
                f"Item ID: {item['Item_ID']}\n"
                f"Stock: {item['Current_Stock']}\n"
                f"Min Stock: {item.get('Min_Stock', 'N/A')}\n"
            )
            if role == "manager":
                detail += f"Purchase Price: ₹{item.get('Purchase_Price', 'N/A')}\n"
                supplier = get_supplier(str(item.get("Supplier_ID", "")))
                if supplier:
                    detail += f"Supplier: {supplier['Name']} ({supplier['Contact_Number']})\n"
            send_text(phone, detail)
            reset_session(phone)
            return
            
        # Multiple matches
        rows = []
        for item in matches[:10]: # Max 10 rows for list message
            desc = f"Stock: {item['Current_Stock']}"
            if role == "manager":
                desc += f" | Price: ₹{item.get('Purchase_Price', 'N/A')}"
            rows.append({
                "id": f"inv_{item['Item_ID']}",
                "title": str(item["Item_Name"])[:24],
                "description": desc[:72],
            })
        
        send_list_message(
            to=phone,
            header="🔍 Search Results",
            body="Multiple items found. Tap to view details.",
            button_text="View Items",
            sections=[{"title": "Matches", "rows": rows}],
        )
        reset_session(phone)
        return

    # Note: awaiting_item_id is replaced by awaiting_action_search_term and list selections

    # Step 2 — collect quantity
    if state == "awaiting_quantity":
        if not text.strip().isdigit() or int(text.strip()) <= 0:
            send_text(phone, "⚠️ Please enter a valid positive number.")
            return
        qty = int(text.strip())
        item_id = session["item_id"]
        item_name = session["item_name"]
        current_stock = session["current_stock"]
        min_stock = session["min_stock"]
        supplier_id = session["supplier_id"]

        if action == "Deduct" and qty > current_stock:
            send_text(
                phone,
                f"⚠️ Cannot deduct {qty} — only {current_stock} in stock.\n"
                "Enter a smaller number or type *cancel*.",
            )
            return

        # ---- Worker: create approval request ----------------------------------
        if role == "worker":
            req_id = create_approval(phone, item_id, action, qty)
            send_text(
                phone,
                f"✅ *Request submitted!*\n\n"
                f"Request ID: {req_id}\n"
                f"Item: {item_name}\n"
                f"Action: {action} {qty} units\n\n"
                "Waiting for Manager approval.",
            )
            # Notify Manager
            manager_phone = get_manager_phone()
            if manager_phone:
                body = (
                    f"📋 *New Approval Request*\n\n"
                    f"Request: {req_id}\n"
                    f"Worker: {phone}\n"
                    f"Item: {item_name} ({item_id})\n"
                    f"Action: {action} {qty} units"
                )
                send_button_message(
                    to=manager_phone,
                    body=body,
                    buttons=[
                        {"id": f"approve_{req_id}", "title": "✅ Approve"},
                        {"id": f"reject_{req_id}", "title": "❌ Reject"},
                    ],
                )
            reset_session(phone)
            return

        # ---- Manager: direct update ------------------------------------------
        if role == "manager":
            new_stock = (
                current_stock + qty if action == "Add" else current_stock - qty
            )
            update_inventory_stock(item_id, new_stock)
            log_history(item_id, item_name, action, qty, phone, current_stock, new_stock)
            send_text(
                phone,
                f"✅ *Inventory updated!*\n\n"
                f"Item: {item_name}\n"
                f"Action: {action} {qty}\n"
                f"New stock: {new_stock}",
            )
            # JIT check for deductions
            if action == "Deduct":
                _jit_check(phone, item_id, item_name, new_stock, min_stock, supplier_id)
            reset_session(phone)
            return


# ---------------------------------------------------------------------------
# Interactive message handler (button & list replies)
# ---------------------------------------------------------------------------

def handle_interactive(phone: str, interactive_data: dict):
    """Handle Interactive message replies (buttons & list selections)."""
    msg_type = interactive_data.get("type")

    if msg_type == "button_reply":
        button_id = interactive_data["button_reply"]["id"]
        _handle_button_reply(phone, button_id)

    elif msg_type == "list_reply":
        list_id = interactive_data["list_reply"]["id"]
        _handle_list_reply(phone, list_id)


def _handle_list_reply(phone: str, list_id: str):
    """Process a list-selection reply."""
    user = get_user(phone)
    role = str(user.get("Role", "")).strip().lower() if user else "worker"

    # Menu commands
    if list_id == "cmd_more":
        _send_more_menu(phone, role)
    elif list_id == "cmd_new_item":
        user_sessions[phone] = {"state": "awaiting_new_item_name", "action": "AddNewItem"}
        send_text(phone, "➕ *Add New Item*\n\nWhat is the *Name* of the new item?")
    elif list_id.startswith("sel_sup_") and user_sessions.get(phone, {}).get("state") == "awaiting_new_item_supplier":
        sup_id = list_id.replace("sel_sup_", "")
        if sup_id == "NONE":
            sup_id = ""
        
        session = user_sessions[phone]
        name = session["new_item_name"]
        price = session["new_item_price"]
        min_stock = session["new_item_min_stock"]
        initial_stock = session["new_item_initial_stock"]
        
        ws = _worksheet("Inventory")
        records = ws.get_all_records()
        max_num = 0
        for r in records:
            item_id = str(r.get("Item_ID", ""))
            if item_id.startswith("ITEM-"):
                num = item_id.replace("ITEM-", "")
                if num.isdigit() and int(num) > max_num:
                    max_num = int(num)
        new_id = f"ITEM-{max_num + 1}"
        
        ws.append_row([new_id, name, initial_stock, min_stock, price, sup_id])
        log_history(new_id, name, "Create", initial_stock, phone, 0, initial_stock)
        
        send_text(phone, f"✅ *Item Created!*\n\nID: {new_id}\nName: {name}\nStock: {initial_stock}\nPrice: ₹{price}\nSupplier: {sup_id}")
        reset_session(phone)
    elif list_id == "cmd_view":
        _send_inventory_list(phone, role)
    elif list_id == "cmd_search":
        user_sessions[phone] = {"state": "awaiting_search_term", "action": "Search"}
        send_text(phone, "🔍 *Search Item*\n\nPlease enter the *Item ID* or *Item Name*:")
    elif list_id == "cmd_history" and role == "manager":
        recent = get_recent_history(5)
        if not recent:
            send_text(phone, "No recent history found.")
            return
        msg = "🕒 *Recent History*\n\n"
        for r in recent:
            msg += f"• {r['Timestamp']} - {r['Action']} {r['Quantity']} {r['Item_Name']} by {r['Editor_Phone']}\n"
        send_text(phone, msg)
    elif list_id == "cmd_order" and role == "manager":
        user_sessions[phone] = {"state": "awaiting_action_search_term", "action": "Order"}
        send_text(phone, "🛒 *Order Stock*\n\nPlease enter a search term for the item (or type 'all'):")
    elif list_id == "cmd_add_dealer" and role == "manager":
        user_sessions[phone] = {"state": "awaiting_dealer_name", "action": "AddDealer"}
        send_text(phone, "➕ *Add Dealer*\n\nPlease enter the *Dealer's Name*:")
    elif list_id == "cmd_add":
        user_sessions[phone] = {"state": "awaiting_action_search_term", "action": "Add"}
        send_text(phone, "📝 *Add Stock*\n\nPlease enter a search term for the item (or type 'all'):")
    elif list_id == "cmd_deduct":
        user_sessions[phone] = {"state": "awaiting_action_search_term", "action": "Deduct"}
        send_text(phone, "📝 *Deduct Stock*\n\nPlease enter a search term for the item (or type 'all'):")
    elif list_id == "cmd_pending":
        _send_pending_approvals(phone)
    elif list_id.startswith("inv_"):
        # Item detail view
        item_id = list_id.replace("inv_", "")
        item = get_inventory_item(item_id)
        if item:
            detail = (
                f"📦 *{item['Item_Name']}*\n\n"
                f"Item ID: {item['Item_ID']}\n"
                f"Stock: {item['Current_Stock']}\n"
                f"Min Stock: {item.get('Min_Stock', 'N/A')}\n"
            )
            if role == "manager":
                detail += f"Purchase Price: ₹{item.get('Purchase_Price', 'N/A')}\n"
                supplier = get_supplier(str(item.get("Supplier_ID", "")))
                if supplier:
                    detail += f"Supplier: {supplier['Name']} ({supplier['Contact_Number']})\n"
            send_text(phone, detail)
        else:
            send_text(phone, "⚠️ Item not found.")

    elif list_id.startswith("sel_item_"):
        item_id = list_id.replace("sel_item_", "")
        item = get_inventory_item(item_id)
        if not item:
            send_text(phone, "⚠️ Item not found.")
            return
        
        action = user_sessions.get(phone, {}).get("action", "")
        if action in ("Add", "Deduct"):
            user_sessions[phone]["item_id"] = str(item["Item_ID"])
            user_sessions[phone]["item_name"] = item["Item_Name"]
            user_sessions[phone]["current_stock"] = int(item["Current_Stock"])
            user_sessions[phone]["min_stock"] = int(item.get("Min_Stock", 0))
            user_sessions[phone]["supplier_id"] = str(item.get("Supplier_ID", ""))
            user_sessions[phone]["state"] = "awaiting_quantity"
            send_text(
                phone,
                f"Item: *{item['Item_Name']}*  (current stock: {item['Current_Stock']})\n\n"
                f"Enter the *quantity* to {action.lower()}:"
            )
        elif action == "Order":
            supplier_id_raw = str(item.get("Supplier_ID", ""))
            if not supplier_id_raw:
                send_text(phone, f"⚠️ No supplier found for item {item['Item_Name']}. Type *menu* to exit.")
                reset_session(phone)
                return
            
            # Check for multiple suppliers
            supplier_ids = [s.strip() for s in supplier_id_raw.split(",") if s.strip()]
            if len(supplier_ids) > 1:
                rows = []
                for s_id in supplier_ids:
                    sup = get_supplier(s_id)
                    if sup:
                        rows.append({
                            "id": f"sel_sup_{s_id}",
                            "title": str(sup["Name"])[:24],
                            "description": str(sup["Contact_Number"])[:72]
                        })
                if not rows:
                    send_text(phone, "⚠️ Error loading suppliers.")
                    reset_session(phone)
                    return
                user_sessions[phone]["item_name"] = item["Item_Name"]
                user_sessions[phone]["state"] = "awaiting_supplier_selection"
                send_list_message(
                    to=phone,
                    header="🛒 Select Supplier",
                    body="This item has multiple dealers. Select one:",
                    button_text="Dealers",
                    sections=[{"title": "Suppliers", "rows": rows[:10]}]
                )
            else:
                supplier = get_supplier(supplier_ids[0])
                if not supplier:
                    send_text(phone, f"⚠️ No valid supplier found. Type *menu* to exit.")
                    reset_session(phone)
                    return
                user_sessions[phone]["item_name"] = item["Item_Name"]
                user_sessions[phone]["supplier_number"] = str(supplier["Contact_Number"]).strip().lstrip("+")
                user_sessions[phone]["supplier_name"] = supplier["Name"]
                user_sessions[phone]["state"] = "awaiting_order_prompt"
                send_text(
                    phone,
                    f"🛒 *Order {item['Item_Name']}*\n"
                    f"Supplier: {supplier['Name']}\n\n"
                    "Please type the *message/prompt* you want to send to the supplier:"
                )

    elif list_id.startswith("sel_sup_"):
        s_id = list_id.replace("sel_sup_", "")
        supplier = get_supplier(s_id)
        if not supplier:
            send_text(phone, "⚠️ Supplier not found.")
            return
        user_sessions[phone]["supplier_number"] = str(supplier["Contact_Number"]).strip().lstrip("+")
        user_sessions[phone]["supplier_name"] = supplier["Name"]
        user_sessions[phone]["state"] = "awaiting_order_prompt"
        item_name = user_sessions[phone].get("item_name", "Unknown Item")
        send_text(
            phone,
            f"🛒 *Order {item_name}*\n"
            f"Supplier: {supplier['Name']}\n\n"
            "Please type the *message/prompt* you want to send to the supplier:"
        )


def _handle_button_reply(phone: str, button_id: str):
    """Process Approve / Reject button clicks."""
    user = get_user(phone)
    if not user or str(user.get("Role", "")).strip().lower() != "manager":
        send_text(phone, "⛔ Only Managers can approve or reject requests.")
        return

    if button_id.startswith("approve_"):
        request_id = button_id.replace("approve_", "")
        _process_approval(phone, request_id, approved=True)

    elif button_id.startswith("reject_"):
        request_id = button_id.replace("reject_", "")
        _process_approval(phone, request_id, approved=False)


def _process_approval(manager_phone: str, request_id: str, approved: bool):
    """Approve or reject a pending request and update sheets accordingly."""
    approval = get_approval(request_id)
    if approval is None:
        send_text(manager_phone, f"⚠️ Request *{request_id}* not found.")
        return

    if str(approval.get("Status", "")).strip().lower() != "pending":
        send_text(
            manager_phone,
            f"ℹ️ Request *{request_id}* has already been *{approval['Status']}*.",
        )
        return

    worker_phone = str(approval["Worker_Number"]).strip()
    item_id = str(approval["Item_ID"]).strip()
    action = str(approval["Action"]).strip()
    qty = int(approval["Quantity"])
    item = get_inventory_item(item_id)

    if not approved:
        update_approval_status(request_id, "Rejected")
        send_text(manager_phone, f"❌ Request *{request_id}* has been *Rejected*.")
        send_text(
            worker_phone,
            f"❌ Your request *{request_id}* ({action} {qty} of {item['Item_Name'] if item else item_id}) "
            "was *Rejected* by the Manager.",
        )
        return

    # Approved — update inventory
    if item is None:
        send_text(manager_phone, f"⚠️ Item *{item_id}* no longer exists in inventory.")
        return

    current_stock = int(item["Current_Stock"])
    if action.lower() == "add":
        new_stock = current_stock + qty
    else:
        new_stock = current_stock - qty
        if new_stock < 0:
            send_text(
                manager_phone,
                f"⚠️ Cannot deduct {qty} — only {current_stock} in stock. Request not processed.",
            )
            return

    update_inventory_stock(item_id, new_stock)
    update_approval_status(request_id, "Approved")
    log_history(item_id, item["Item_Name"], action, qty, manager_phone, current_stock, new_stock)

    send_text(
        manager_phone,
        f"✅ Request *{request_id}* — *Approved*\n\n"
        f"Item: {item['Item_Name']}\n"
        f"Action: {action} {qty}\n"
        f"New stock: {new_stock}",
    )
    send_text(
        worker_phone,
        f"✅ Your request *{request_id}* ({action} {qty} of {item['Item_Name']}) "
        "has been *Approved*!\n"
        f"Updated stock: {new_stock}",
    )

    # JIT wholesaler trigger
    if action.lower() == "deduct":
        min_stock = int(item.get("Min_Stock", 0))
        supplier_id = str(item.get("Supplier_ID", ""))
        _jit_check(manager_phone, item_id, item["Item_Name"], new_stock, min_stock, supplier_id)


# ---------------------------------------------------------------------------
# JIT Wholesaler Trigger
# ---------------------------------------------------------------------------

def _jit_check(manager_phone: str, item_id: str, item_name: str, new_stock: int, min_stock: int, supplier_id: str):
    """If stock falls below Min_Stock, alert the Manager with a wa.me link
    to the item's supplier."""
    if new_stock >= min_stock:
        return

    supplier_ids = [s.strip() for s in supplier_id.split(",") if s.strip()]
    if not supplier_ids:
        send_text(
            manager_phone,
            f"⚠️ *Low-stock alert!*\n\n"
            f"Item: {item_name} ({item_id})\n"
            f"Stock: {new_stock} (min: {min_stock})\n\n"
            "No supplier found on file — please reorder manually.",
        )
        return

    # For JIT, just use the first supplier
    supplier = get_supplier(supplier_ids[0])
    if not supplier:
        return

    supplier_number = str(supplier["Contact_Number"]).strip().lstrip("+")
    supplier_name = supplier["Name"]
    reorder_text = f"Hi {supplier_name}, I'd like to reorder *{item_name}* (ID: {item_id}). Current stock is {new_stock}."
    wa_link = f"https://wa.me/{supplier_number}?text={requests.utils.quote(reorder_text)}"

    send_text(
        manager_phone,
        f"🚨 *LOW STOCK ALERT*\n\n"
        f"Item: {item_name} ({item_id})\n"
        f"Current Stock: {new_stock}\n"
        f"Minimum Required: {min_stock}\n\n"
        f"Supplier: {supplier_name}\n"
        f"📲 Tap to reorder:\n{wa_link}",
    )


# ---------------------------------------------------------------------------
# Flask routes
# ---------------------------------------------------------------------------

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    """Meta webhook verification (challenge–response)."""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        logger.info("Webhook verified successfully.")
        return challenge, 200
    logger.warning("Webhook verification failed.")
    return "Forbidden", 403


@app.route("/webhook", methods=["POST"])
def process_webhook():
    """Receive and process inbound WhatsApp messages."""
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"status": "no data"}), 400

    try:
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})

                # Ignore status updates (message delivery receipts, etc.)
                if "messages" not in value:
                    continue

                for msg in value["messages"]:
                    phone = msg.get("from", "")
                    msg_type = msg.get("type", "")

                    if msg_type == "text":
                        text = msg["text"]["body"]
                        logger.info("Text from %s: %s", phone, text)
                        handle_message(phone, text)

                    elif msg_type == "interactive":
                        interactive_data = msg.get("interactive", {})
                        logger.info("Interactive from %s: %s", phone, json.dumps(interactive_data))
                        handle_interactive(phone, interactive_data)

                    else:
                        # Unsupported message type
                        send_text(phone, "🤖 I can only process text and interactive messages. Type *menu* to begin.")

    except Exception:
        logger.exception("Error processing webhook payload")

    # Always return 200 to Meta to avoid retries
    return jsonify({"status": "ok"}), 200


@app.route("/health", methods=["GET"])
def health():
    """Simple health-check endpoint."""
    return jsonify({"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}), 200


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
