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

import google.generativeai as genai

WHATSAPP_TOKEN = os.environ["WHATSAPP_TOKEN"]
WHATSAPP_PHONE_ID = os.environ["WHATSAPP_PHONE_ID"]
VERIFY_TOKEN = os.environ["VERIFY_TOKEN"]
GOOGLE_SHEET_ID = os.environ["GOOGLE_SHEET_ID"]
GOOGLE_CREDENTIALS_FILE = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

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
    logger.info("send_text → %s | status=%s | response=%s", to, resp.status_code, resp.text)
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

    # Only keep the pending check for managers
    if text_lower == "pending" and role == "manager":
        _send_pending_approvals(phone)
        return

    # Fallback to AI Processing for everything
    if GEMINI_API_KEY:
        send_text(phone, "🤖 AI is thinking...")
        ai_resp = process_with_gemini(phone, None, None, text)
        propose_ai_actions(phone, ai_resp)
    else:
        send_text(
            phone,
            "🤖 I didn't understand that.\n\n"
            "Please provide a GEMINI_API_KEY.",
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

# ---------------------------------------------------------------------------
# Interactive message handler (button & list replies)
# ---------------------------------------------------------------------------

def handle_interactive(phone: str, interactive_data: dict):
    """Handle Interactive message replies (buttons & list selections)."""
    msg_type = interactive_data.get("type")

    if msg_type == "button_reply":
        button_id = interactive_data["button_reply"]["id"]
        _handle_button_reply(phone, button_id)


def _handle_button_reply(phone: str, button_id: str):
    """Process Approve / Reject button clicks and AI confirmation."""
    if button_id == "ai_confirm_yes":
        session = user_sessions.get(phone)
        if session and session.get("state") == "awaiting_ai_confirm":
            actions = session.get("pending_actions", [])
            execute_ai_actions(phone, actions)
            reset_session(phone)
        else:
            send_text(phone, "🤖 This action has expired.")
        return
        
    if button_id == "ai_confirm_no":
        send_text(phone, "❌ AI updates cancelled.")
        reset_session(phone)
        return

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
# AI Processing (Gemini)
# ---------------------------------------------------------------------------

import tempfile

def _download_whatsapp_media(media_id: str) -> tuple[str, str]:
    """Download media from WhatsApp servers."""
    url = f"https://graph.facebook.com/v21.0/{media_id}"
    resp = requests.get(url, headers=_wa_headers())
    if resp.status_code != 200:
        logger.error(f"Failed to get media url: {resp.text}")
        return None, None
        
    data = resp.json()
    media_url = data.get("url")
    mime_type = data.get("mime_type")
    
    file_resp = requests.get(media_url, headers=_wa_headers())
    if file_resp.status_code != 200:
        logger.error(f"Failed to download media file: {file_resp.text}")
        return None, None

    # Map MIME to a sensible extension
    ext_map = {
        "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
        "audio/ogg": ".ogg", "audio/mpeg": ".mp3", "audio/mp4": ".m4a",
        "audio/amr": ".amr", "audio/aac": ".aac",
    }
    # Strip codec parameters (e.g. "audio/ogg; codecs=opus" → "audio/ogg")
    clean_mime = mime_type.split(";")[0].strip() if mime_type else "application/octet-stream"
    ext = ext_map.get(clean_mime, ".bin")

    fd, filepath = tempfile.mkstemp(suffix=ext)
    with os.fdopen(fd, 'wb') as f:
        f.write(file_resp.content)
        
    return filepath, clean_mime

def process_with_gemini(phone: str, file_path: str, mime_type: str, user_text: str = None) -> str:
    """Send text, image, or audio to Gemini to converse or parse actions."""
    items = get_all_inventory()
    items_str = json.dumps([{"id": i["Item_ID"], "name": i["Item_Name"], "stock": i["Current_Stock"], "min": i.get("Min_Stock", 0), "price": i.get("Purchase_Price", 0), "sup_id": i.get("Supplier_ID", "")} for i in items])
    try:
        suppliers = _worksheet("Suppliers").get_all_records()
        sup_str = json.dumps([{"id": s["Supplier_ID"], "name": s["Name"]} for s in suppliers])
    except:
        sup_str = "[]"
    
    prompt_context = f"""
    You are an AI inventory assistant chatting over WhatsApp. 
    Current inventory: {items_str}
    Current suppliers: {sup_str}
    
    Your goal is to gather information to execute an inventory update (Add stock, Deduct stock, or Create a new item).
    If the user just says "Add stock", ask them what item and quantity.
    If they provide an image of a bill, extract the items and assume action is "Add" (receiving new stock), and ask them to confirm.
    
    You MUST ALWAYS respond with a structured JSON object in EXACTLY this format (no markdown code blocks, just raw JSON):
    {{
      "reply_to_user": "Your conversational reply asking for clarification or confirming details.",
      "is_ready_to_execute": false,
      "actions": []
    }}
    
    When the user has confirmed they want to proceed and you have ALL details (Item, Action, Quantity), set "is_ready_to_execute" to true and populate "actions" with:
    [{{"action": "Add"|"Deduct"|"Create", "item_id": "ITEM-X", "quantity": 10, "supplier_name": "Supplier Name", "new_item_name": "If Create", "new_item_price": 0, "new_item_min_stock": 0}}]
    """
    
    try:
        import google.generativeai as genai
        
        # Dynamically find the best available model
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        target_model = None
        
        # Try to find a 1.5 flash or pro model first
        for m in available_models:
            if '1.5-flash' in m:
                target_model = m
                break
        
        if not target_model:
            for m in available_models:
                if 'gemini' in m and 'vision' not in m:
                    target_model = m
                    break
                    
        if not target_model and available_models:
            target_model = available_models[0]

        model = genai.GenerativeModel(target_model or 'gemini-1.5-flash')
        
        if phone not in user_sessions:
            user_sessions[phone] = {}
        history = user_sessions[phone].get("history", [])
        
        chat = model.start_chat(history=history)

        # Build a more useful default prompt based on the media type
        if user_text:
            user_part = user_text
        elif mime_type and "audio" in mime_type:
            user_part = "The user sent a voice note. Please transcribe it and treat the transcription as their message. Respond accordingly."
        else:
            user_part = "Please analyze the attached file (likely a bill or receipt). Extract the items and quantities."

        current_message = prompt_context + "\n\nUSER MESSAGE:\n" + user_part
        
        if file_path:
            gemini_file = genai.upload_file(path=file_path, mime_type=mime_type)
            response = chat.send_message([gemini_file, current_message])
            genai.delete_file(gemini_file.name)
            os.remove(file_path)
        else:
            response = chat.send_message(current_message)
            
        # Store last 10 turns
        user_sessions[phone]["history"] = chat.history[-10:]
        
        return response.text
    except Exception as e:
        logger.error(f"Gemini API Error: {e}")
        return "{}"

def propose_ai_actions(phone: str, actions_json: str):
    """Parse Gemini JSON. Send conversational reply and show buttons if ready."""
    try:
        clean_json = actions_json.strip()
        if clean_json.startswith("```json"):
            clean_json = clean_json[7:-3]
        elif clean_json.startswith("```"):
            clean_json = clean_json[3:-3]
            
        data = json.loads(clean_json.strip())
        
        reply = data.get("reply_to_user", "I didn't understand that.")
        ready = data.get("is_ready_to_execute", False)
        actions = data.get("actions", [])
        
        if not ready or not actions:
            send_text(phone, "🤖 " + reply)
            return

        user_sessions[phone]["state"] = "awaiting_ai_confirm"
        user_sessions[phone]["pending_actions"] = actions
        
        send_button_message(
            to=phone,
            body=f"🤖 {reply}\n\n*Ready to apply changes?*",
            buttons=[
                {"id": "ai_confirm_yes", "title": "✅ Yes, apply"},
                {"id": "ai_confirm_no", "title": "❌ Cancel"}
            ]
        )
            
    except Exception as e:
        logger.error(f"AI Parse Error: {e}\nRaw output: {actions_json}")
        send_text(phone, "🤖 Sorry, I got confused. What did you want to do?")

def execute_ai_actions(phone: str, actions: list):
    """Apply actions or create worker approvals."""
    user = get_user(phone)
    role = str(user.get("Role", "")).strip().lower() if user else "worker"
    
    try:
        results = []
        for act in actions:
            action = act.get("action", "").capitalize()
            qty = int(act.get("quantity", 0))
            
            if action == "Create":
                if role != "manager":
                    results.append("⛔ Only Managers can create new items.")
                    continue
                name = act.get("new_item_name", "Unknown Item")
                price = int(act.get("new_item_price", 0))
                min_stock = int(act.get("new_item_min_stock", 0))
                
                ws = _worksheet("Inventory")
                records = ws.get_all_records()
                max_num = max([int(str(r.get("Item_ID", "ITEM-0")).replace("ITEM-", "")) for r in records if str(r.get("Item_ID", "")).startswith("ITEM-")] + [0])
                new_id = f"ITEM-{max_num + 1}"
                
                ws.append_row([new_id, name, qty, min_stock, price, ""])
                log_history(new_id, name, "Create", qty, phone, 0, qty)
                results.append(f"✅ Created {name} (ID: {new_id}, Stock: {qty})")
                continue

            if action in ["Add", "Deduct"]:
                item_id = act.get("item_id")
                item = get_inventory_item(item_id)
                if not item:
                    results.append(f"⚠️ Could not find item {item_id}")
                    continue
                    
                if role == "worker":
                    req_id = create_approval(phone, item_id, action, qty)
                    results.append(f"✅ Requested {action} {qty} for {item['Item_Name']}")
                    manager_phone = get_manager_phone()
                    if manager_phone:
                        body = (f"📋 *New AI Request*\n\nRequest: {req_id}\nWorker: {phone}\n"
                                f"Item: {item['Item_Name']}\nAction: {action} {qty} units")
                        send_button_message(
                            to=manager_phone, body=body,
                            buttons=[
                                {"id": f"approve_{req_id}", "title": "✅ Approve"},
                                {"id": f"reject_{req_id}", "title": "❌ Reject"},
                            ]
                        )
                else:
                    current_stock = int(item["Current_Stock"])
                    new_stock = current_stock + qty if action == "Add" else current_stock - qty
                    update_inventory_stock(item_id, new_stock)
                    log_history(item_id, item["Item_Name"], action, qty, phone, current_stock, new_stock)
                    results.append(f"✅ {action} {qty} {item['Item_Name']} (New stock: {new_stock})")
                    
        if results:
            send_text(phone, "🤖 *Summary:*\n" + "\n".join(results))
    except Exception as e:
        logger.error(f"AI Execute Error: {e}")
        send_text(phone, "🤖 Error applying updates.")

# ---------------------------------------------------------------------------
# Flask routes
# ---------------------------------------------------------------------------

@app.route("/models", methods=["GET"])
def get_models():
    """Debug route to list available Gemini models."""
    try:
        import google.generativeai as genai
        models = [m.name for m in genai.list_models()]
        return jsonify({"models": models})
    except Exception as e:
        return jsonify({"error": str(e)})

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

                    elif msg_type in ("image", "audio", "voice"):
                        if not GEMINI_API_KEY:
                            send_text(phone, "🤖 AI is currently disabled. Please provide a GEMINI_API_KEY.")
                            continue
                            
                        send_text(phone, f"🤖 AI is processing your {msg_type}...")
                        media_id = msg[msg_type]["id"]
                        file_path, mime_type = _download_whatsapp_media(media_id)
                        if file_path:
                            ai_resp = process_with_gemini(phone, file_path, mime_type)
                            propose_ai_actions(phone, ai_resp)
                        else:
                            send_text(phone, "🤖 Failed to download media.")
                            
                    else:
                        # Pass unsupported types to AI to handle naturally
                        if GEMINI_API_KEY:
                            send_text(phone, "🤖 AI is thinking...")
                            ai_resp = process_with_gemini(phone, None, None, f"(System note: User sent a '{msg_type}' message which is unsupported. Tell them you only accept text, voice notes, and images.)")
                            propose_ai_actions(phone, ai_resp)

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
