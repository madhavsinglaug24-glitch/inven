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
# 🌐 Internationalization (i18n)
# ---------------------------------------------------------------------------
# Per-user language preference (in-memory, keyed by phone)
user_lang: dict[str, str] = {}

DEFAULT_LANG = "en"

STRINGS = {
    "en": {
        # ── General ──
        "not_registered":       "🚫 Looks like you're not in the system yet — reach out to your Manager to get set up.",
        "ai_thinking":          "✨ Working on it…",
        "ai_disabled":          "🔌 AI features are offline right now. An admin needs to configure the GEMINI_API_KEY.",
        "ai_processing_media":  "🔍 Analyzing your {media_type} — hang tight…",
        "ai_download_fail":     "📥 Couldn't grab that file. Mind sending it again?",
        "ai_expired":           "⏳ That action already expired — send your request again to start fresh.",
        "ai_cancelled":         "🙅 Got it — changes discarded.",
        "ai_confused":          "🤔 Hmm, I didn't quite catch that. Could you rephrase what you'd like to do?",
        "ai_error":             "⚡ Something went wrong on my end. Try again in a sec.",
        "ai_summary":           "📊 *Here's what happened:*\n",
        "ai_confirm_prompt":    "*Want me to go ahead and apply these changes?*",
        "btn_yes":              "✅ Apply",
        "btn_cancel":           "❌ Cancel",
        "unsupported_msg":      "(System note: User sent a '{msg_type}' message which isn't supported. Let them know you can handle text, voice notes, and images.)",

        # ── Manager / Approvals ──
        "managers_only":        "🔒 This action is reserved for Managers.",
        "no_pending":           "🎉 All clear — no pending requests right now.",
        "request_not_found":    "🔎 Couldn't find request *{request_id}*.",
        "request_already":      "ℹ️ Request *{request_id}* was already *{status}*.",
        "request_rejected_mgr": "✖️ Request *{request_id}* — *Rejected*",
        "request_rejected_wkr": "✖️ Your request *{request_id}* ({action} {qty}× {item_name}) was *declined* by the Manager.",
        "item_missing":         "🔎 Item *{item_id}* doesn't seem to exist in inventory anymore.",
        "stock_insufficient":   "📉 Can't deduct {qty} — only *{stock}* left in stock.",
        "request_approved_mgr": "✅ Request *{request_id}* — *Approved*\n\n📦 {item_name}\n🔄 {action} {qty}\n📊 Updated stock: {new_stock}",
        "request_approved_wkr": "🎉 Great news! Your request *{request_id}* ({action} {qty}× {item_name}) was *approved*.\n📊 Stock is now: {new_stock}",
        "pending_header":       "📋 *Request {request_id}*\n👤 Worker: {worker}\n📦 Item: {item_name} ({item_id})\n🔄 {action} — {qty} units",
        "btn_approve":          "✅ Approve",
        "btn_reject":           "❌ Reject",
        "new_request_header":   "📬 *Incoming Request*\n\n🆔 {req_id}\n👤 From: {phone}\n📦 {item_name}\n🔄 {action} — {qty} units",

        # ── JIT / Low Stock ──
        "low_stock_no_supplier":"⚡ *Heads up — low stock!*\n\n📦 {item_name} ({item_id})\n📊 Stock: {stock} (minimum: {min_stock})\n\nNo supplier on file — manual reorder needed.",
        "low_stock_alert":      "🚨 *Low Stock Alert*\n\n📦 {item_name} ({item_id})\n📊 Current: {stock}\n📉 Minimum: {min_stock}\n\n🏭 Supplier: {supplier_name}\n📲 Tap to reorder:\n{wa_link}",

        # ── AI Actions ──
        "create_mgr_only":      "🔒 Only Managers can create new inventory items.",
        "created_item":         "✅ Created *{name}* — ID: `{item_id}`, Stock: {qty}",
        "item_not_found":       "🔎 Couldn't find item `{item_id}` in inventory.",
        "requested_action":     "📩 Submitted: {action} {qty}× *{item_name}* — awaiting approval.",
        "action_done":          "✅ Done — {action} {qty}× *{item_name}* → Stock: {new_stock}",

        # ── Language ──
        "lang_switched":        "🌐 Language set to *English* 🇬🇧",
        "lang_help":            "🌐 *Switch language:*\nType one of:\n• `lang en` — English 🇬🇧\n• `lang hi` — हिन्दी 🇮🇳\n• `lang pa` — ਪੰਜਾਬੀ 🇮🇳",
    },
    "hi": {
        # ── General ──
        "not_registered":       "🚫 लगता है आप अभी सिस्टम में नहीं हैं — सेटअप के लिए अपने मैनेजर से संपर्क करें।",
        "ai_thinking":          "✨ प्रोसेस हो रहा है…",
        "ai_disabled":          "🔌 AI अभी ऑफ़लाइन है। एडमिन को GEMINI_API_KEY सेट करना होगा।",
        "ai_processing_media":  "🔍 आपकी {media_type} एनालाइज़ कर रहे हैं — रुकिए…",
        "ai_download_fail":     "📥 फ़ाइल डाउनलोड नहीं हो सकी। दोबारा भेजें?",
        "ai_expired":           "⏳ यह एक्शन एक्सपायर हो गया — नई रिक्वेस्ट भेजें।",
        "ai_cancelled":         "🙅 ठीक है — बदलाव रद्द कर दिए।",
        "ai_confused":          "🤔 समझ नहीं आया। क्या करना चाहते हैं, दोबारा बताएं?",
        "ai_error":             "⚡ कुछ गड़बड़ हो गई। थोड़ी देर में फिर कोशिश करें।",
        "ai_summary":           "📊 *यह रहा सारांश:*\n",
        "ai_confirm_prompt":    "*क्या ये बदलाव लागू करूं?*",
        "btn_yes":              "✅ हां करो",
        "btn_cancel":           "❌ रद्द करो",
        "unsupported_msg":      "(System note: User sent a '{msg_type}' message which isn't supported. Reply in Hindi. Let them know you can handle text, voice notes, and images.)",

        # ── Manager / Approvals ──
        "managers_only":        "🔒 यह एक्शन सिर्फ़ मैनेजर के लिए है।",
        "no_pending":           "🎉 कोई पेंडिंग रिक्वेस्ट नहीं है।",
        "request_not_found":    "🔎 रिक्वेस्ट *{request_id}* नहीं मिली।",
        "request_already":      "ℹ️ रिक्वेस्ट *{request_id}* पहले ही *{status}* हो चुकी है।",
        "request_rejected_mgr": "✖️ रिक्वेस्ट *{request_id}* — *अस्वीकृत*",
        "request_rejected_wkr": "✖️ आपकी रिक्वेस्ट *{request_id}* ({action} {qty}× {item_name}) मैनेजर ने *अस्वीकृत* कर दी।",
        "item_missing":         "🔎 आइटम *{item_id}* इन्वेंटरी में नहीं मिला।",
        "stock_insufficient":   "📉 {qty} नहीं घटा सकते — स्टॉक में सिर्फ़ *{stock}* बचे हैं।",
        "request_approved_mgr": "✅ रिक्वेस्ट *{request_id}* — *स्वीकृत*\n\n📦 {item_name}\n🔄 {action} {qty}\n📊 नया स्टॉक: {new_stock}",
        "request_approved_wkr": "🎉 बधाई! आपकी रिक्वेस्ट *{request_id}* ({action} {qty}× {item_name}) *स्वीकृत* हो गई।\n📊 स्टॉक अब: {new_stock}",
        "pending_header":       "📋 *रिक्वेस्ट {request_id}*\n👤 वर्कर: {worker}\n📦 आइटम: {item_name} ({item_id})\n🔄 {action} — {qty} यूनिट",
        "btn_approve":          "✅ मंज़ूर",
        "btn_reject":           "❌ अस्वीकार",
        "new_request_header":   "📬 *नई रिक्वेस्ट*\n\n🆔 {req_id}\n👤 वर्कर: {phone}\n📦 {item_name}\n🔄 {action} — {qty} यूनिट",

        # ── JIT / Low Stock ──
        "low_stock_no_supplier":"⚡ *ध्यान दें — स्टॉक कम है!*\n\n📦 {item_name} ({item_id})\n📊 स्टॉक: {stock} (न्यूनतम: {min_stock})\n\nसप्लायर नहीं मिला — मैन्युअल ऑर्डर करें।",
        "low_stock_alert":      "🚨 *स्टॉक कम है!*\n\n📦 {item_name} ({item_id})\n📊 मौजूदा: {stock}\n📉 न्यूनतम: {min_stock}\n\n🏭 सप्लायर: {supplier_name}\n📲 ऑर्डर करने के लिए टैप करें:\n{wa_link}",

        # ── AI Actions ──
        "create_mgr_only":      "🔒 नए आइटम सिर्फ़ मैनेजर बना सकते हैं।",
        "created_item":         "✅ *{name}* बनाया — ID: `{item_id}`, स्टॉक: {qty}",
        "item_not_found":       "🔎 आइटम `{item_id}` नहीं मिला।",
        "requested_action":     "📩 भेजा गया: {action} {qty}× *{item_name}* — मंज़ूरी का इंतज़ार।",
        "action_done":          "✅ हो गया — {action} {qty}× *{item_name}* → स्टॉक: {new_stock}",

        # ── Language ──
        "lang_switched":        "🌐 भाषा *हिन्दी* में सेट की गई 🇮🇳",
        "lang_help":            "🌐 *भाषा बदलें:*\nटाइप करें:\n• `lang en` — English 🇬🇧\n• `lang hi` — हिन्दी 🇮🇳\n• `lang pa` — ਪੰਜਾਬੀ 🇮🇳",
    },
    "pa": {
        # ── General ──
        "not_registered":       "🚫 ਲੱਗਦਾ ਤੁਸੀਂ ਅਜੇ ਸਿਸਟਮ ਵਿੱਚ ਨਹੀਂ ਹੋ — ਸੈੱਟਅੱਪ ਲਈ ਆਪਣੇ ਮੈਨੇਜਰ ਨਾਲ ਗੱਲ ਕਰੋ।",
        "ai_thinking":          "✨ ਕੰਮ ਹੋ ਰਿਹਾ ਏ…",
        "ai_disabled":          "🔌 AI ਹੁਣ ਆਫ਼ਲਾਈਨ ਹੈ। ਐਡਮਿਨ ਨੂੰ GEMINI_API_KEY ਸੈੱਟ ਕਰਨੀ ਪਵੇਗੀ।",
        "ai_processing_media":  "🔍 ਤੁਹਾਡੀ {media_type} ਚੈੱਕ ਕਰ ਰਹੇ ਹਾਂ — ਰੁਕੋ…",
        "ai_download_fail":     "📥 ਫ਼ਾਈਲ ਡਾਊਨਲੋਡ ਨਹੀਂ ਹੋ ਸਕੀ। ਦੁਬਾਰਾ ਭੇਜੋ?",
        "ai_expired":           "⏳ ਇਹ ਐਕਸ਼ਨ ਐਕਸਪਾਇਰ ਹੋ ਗਿਆ — ਨਵੀਂ ਰਿਕਵੈਸਟ ਭੇਜੋ।",
        "ai_cancelled":         "🙅 ਠੀਕ ਹੈ — ਬਦਲਾਅ ਰੱਦ ਕਰ ਦਿੱਤੇ।",
        "ai_confused":          "🤔 ਸਮਝ ਨਹੀਂ ਆਇਆ। ਕੀ ਕਰਨਾ ਚਾਹੁੰਦੇ ਹੋ, ਦੁਬਾਰਾ ਦੱਸੋ?",
        "ai_error":             "⚡ ਕੁਝ ਗੜਬੜ ਹੋ ਗਈ। ਥੋੜੀ ਦੇਰ ਬਾਅਦ ਦੁਬਾਰਾ ਕੋਸ਼ਿਸ਼ ਕਰੋ।",
        "ai_summary":           "📊 *ਇਹ ਰਿਹਾ ਸਾਰ:*\n",
        "ai_confirm_prompt":    "*ਕੀ ਇਹ ਬਦਲਾਅ ਲਾਗੂ ਕਰਾਂ?*",
        "btn_yes":              "✅ ਹਾਂ ਕਰੋ",
        "btn_cancel":           "❌ ਰੱਦ ਕਰੋ",
        "unsupported_msg":      "(System note: User sent a '{msg_type}' message which isn't supported. Reply in Punjabi. Let them know you can handle text, voice notes, and images.)",

        # ── Manager / Approvals ──
        "managers_only":        "🔒 ਇਹ ਐਕਸ਼ਨ ਸਿਰਫ਼ ਮੈਨੇਜਰ ਲਈ ਹੈ।",
        "no_pending":           "🎉 ਕੋਈ ਪੈਂਡਿੰਗ ਰਿਕਵੈਸਟ ਨਹੀਂ।",
        "request_not_found":    "🔎 ਰਿਕਵੈਸਟ *{request_id}* ਨਹੀਂ ਮਿਲੀ।",
        "request_already":      "ℹ️ ਰਿਕਵੈਸਟ *{request_id}* ਪਹਿਲਾਂ ਹੀ *{status}* ਹੋ ਚੁੱਕੀ ਹੈ।",
        "request_rejected_mgr": "✖️ ਰਿਕਵੈਸਟ *{request_id}* — *ਰੱਦ*",
        "request_rejected_wkr": "✖️ ਤੁਹਾਡੀ ਰਿਕਵੈਸਟ *{request_id}* ({action} {qty}× {item_name}) ਮੈਨੇਜਰ ਨੇ *ਰੱਦ* ਕਰ ਦਿੱਤੀ।",
        "item_missing":         "🔎 ਆਈਟਮ *{item_id}* ਇਨਵੈਂਟਰੀ ਵਿੱਚ ਨਹੀਂ ਮਿਲੀ।",
        "stock_insufficient":   "📉 {qty} ਨਹੀਂ ਘਟਾ ਸਕਦੇ — ਸਟਾਕ ਵਿੱਚ ਸਿਰਫ਼ *{stock}* ਹਨ।",
        "request_approved_mgr": "✅ ਰਿਕਵੈਸਟ *{request_id}* — *ਮਨਜ਼ੂਰ*\n\n📦 {item_name}\n🔄 {action} {qty}\n📊 ਨਵਾਂ ਸਟਾਕ: {new_stock}",
        "request_approved_wkr": "🎉 ਵਧਾਈਆਂ! ਤੁਹਾਡੀ ਰਿਕਵੈਸਟ *{request_id}* ({action} {qty}× {item_name}) *ਮਨਜ਼ੂਰ* ਹੋ ਗਈ।\n📊 ਸਟਾਕ ਹੁਣ: {new_stock}",
        "pending_header":       "📋 *ਰਿਕਵੈਸਟ {request_id}*\n👤 ਵਰਕਰ: {worker}\n📦 ਆਈਟਮ: {item_name} ({item_id})\n🔄 {action} — {qty} ਯੂਨਿਟ",
        "btn_approve":          "✅ ਮਨਜ਼ੂਰ",
        "btn_reject":           "❌ ਰੱਦ",
        "new_request_header":   "📬 *ਨਵੀਂ ਰਿਕਵੈਸਟ*\n\n🆔 {req_id}\n👤 ਵਰਕਰ: {phone}\n📦 {item_name}\n🔄 {action} — {qty} ਯੂਨਿਟ",

        # ── JIT / Low Stock ──
        "low_stock_no_supplier":"⚡ *ਧਿਆਨ ਦਿਓ — ਸਟਾਕ ਘੱਟ ਹੈ!*\n\n📦 {item_name} ({item_id})\n📊 ਸਟਾਕ: {stock} (ਘੱਟੋ-ਘੱਟ: {min_stock})\n\nਸਪਲਾਇਰ ਨਹੀਂ ਮਿਲਿਆ — ਮੈਨੂਅਲ ਆਰਡਰ ਕਰੋ।",
        "low_stock_alert":      "🚨 *ਸਟਾਕ ਘੱਟ ਹੈ!*\n\n📦 {item_name} ({item_id})\n📊 ਮੌਜੂਦਾ: {stock}\n📉 ਘੱਟੋ-ਘੱਟ: {min_stock}\n\n🏭 ਸਪਲਾਇਰ: {supplier_name}\n📲 ਆਰਡਰ ਕਰਨ ਲਈ ਟੈਪ ਕਰੋ:\n{wa_link}",

        # ── AI Actions ──
        "create_mgr_only":      "🔒 ਨਵੇਂ ਆਈਟਮ ਸਿਰਫ਼ ਮੈਨੇਜਰ ਬਣਾ ਸਕਦੇ ਹਨ।",
        "created_item":         "✅ *{name}* ਬਣਾਇਆ — ID: `{item_id}`, ਸਟਾਕ: {qty}",
        "item_not_found":       "🔎 ਆਈਟਮ `{item_id}` ਨਹੀਂ ਮਿਲੀ।",
        "requested_action":     "📩 ਭੇਜਿਆ: {action} {qty}× *{item_name}* — ਮਨਜ਼ੂਰੀ ਦੀ ਉਡੀਕ।",
        "action_done":          "✅ ਹੋ ਗਿਆ — {action} {qty}× *{item_name}* → ਸਟਾਕ: {new_stock}",

        # ── Language ──
        "lang_switched":        "🌐 ਭਾਸ਼ਾ *ਪੰਜਾਬੀ* ਵਿੱਚ ਸੈੱਟ ਕੀਤੀ 🇮🇳",
        "lang_help":            "🌐 *ਭਾਸ਼ਾ ਬਦਲੋ:*\nਟਾਈਪ ਕਰੋ:\n• `lang en` — English 🇬🇧\n• `lang hi` — हिन्दी 🇮🇳\n• `lang pa` — ਪੰਜਾਬੀ 🇮🇳",
    },
}

def t(phone: str, key: str, **kwargs) -> str:
    """Get a translated string for the user's preferred language."""
    lang = user_lang.get(phone, DEFAULT_LANG)
    template = STRINGS.get(lang, STRINGS[DEFAULT_LANG]).get(key, STRINGS[DEFAULT_LANG].get(key, key))
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return template


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
    text_lower = text.strip().lower()

    # Language switching (available to everyone, even unregistered)
    if text_lower.startswith("lang"):
        parts = text_lower.split()
        if len(parts) == 2 and parts[1] in STRINGS:
            user_lang[phone] = parts[1]
            send_text(phone, t(phone, "lang_switched"))
        else:
            send_text(phone, t(phone, "lang_help"))
        return

    user = get_user(phone)
    if user is None:
        send_text(phone, t(phone, "not_registered"))
        return

    role = str(user.get("Role", "")).strip().lower()
    name = user.get("Name", "User")

    # Only keep the pending check for managers
    if text_lower == "pending" and role == "manager":
        _send_pending_approvals(phone)
        return

    # Fallback to AI Processing for everything
    if GEMINI_API_KEY:
        send_text(phone, t(phone, "ai_thinking"))
        ai_resp = process_with_gemini(phone, None, None, text)
        propose_ai_actions(phone, ai_resp)
    else:
        send_text(phone, t(phone, "ai_disabled"))

def _send_pending_approvals(phone: str):
    """Show all Pending approval requests to the Manager."""
    ws = _worksheet("Approvals")
    records = ws.get_all_records()
    pending = [r for r in records if str(r.get("Status", "")).strip().lower() == "pending"]

    if not pending:
        send_text(phone, t(phone, "no_pending"))
        return

    for req in pending:
        item = get_inventory_item(req["Item_ID"])
        item_name = item["Item_Name"] if item else req["Item_ID"]
        body = t(phone, "pending_header",
                 request_id=req['Request_ID'], worker=req['Worker_Number'],
                 item_name=item_name, item_id=req['Item_ID'],
                 action=req['Action'], qty=req['Quantity'])
        send_button_message(
            to=phone,
            body=body,
            buttons=[
                {"id": f"approve_{req['Request_ID']}", "title": t(phone, "btn_approve")},
                {"id": f"reject_{req['Request_ID']}", "title": t(phone, "btn_reject")},
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
            send_text(phone, t(phone, "ai_expired"))
        return
        
    if button_id == "ai_confirm_no":
        send_text(phone, t(phone, "ai_cancelled"))
        reset_session(phone)
        return

    user = get_user(phone)
    if not user or str(user.get("Role", "")).strip().lower() != "manager":
        send_text(phone, t(phone, "managers_only"))
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
        send_text(manager_phone, t(manager_phone, "request_not_found", request_id=request_id))
        return

    if str(approval.get("Status", "")).strip().lower() != "pending":
        send_text(manager_phone, t(manager_phone, "request_already", request_id=request_id, status=approval['Status']))
        return

    worker_phone = str(approval["Worker_Number"]).strip()
    item_id = str(approval["Item_ID"]).strip()
    action = str(approval["Action"]).strip()
    qty = int(approval["Quantity"])
    item = get_inventory_item(item_id)
    item_name = item["Item_Name"] if item else item_id

    if not approved:
        update_approval_status(request_id, "Rejected")
        send_text(manager_phone, t(manager_phone, "request_rejected_mgr", request_id=request_id))
        send_text(worker_phone, t(worker_phone, "request_rejected_wkr", request_id=request_id, action=action, qty=qty, item_name=item_name))
        return

    # Approved — update inventory
    if item is None:
        send_text(manager_phone, t(manager_phone, "item_missing", item_id=item_id))
        return

    current_stock = int(item["Current_Stock"])
    if action.lower() == "add":
        new_stock = current_stock + qty
    else:
        new_stock = current_stock - qty
        if new_stock < 0:
            send_text(manager_phone, t(manager_phone, "stock_insufficient", qty=qty, stock=current_stock))
            return

    update_inventory_stock(item_id, new_stock)
    update_approval_status(request_id, "Approved")
    log_history(item_id, item["Item_Name"], action, qty, manager_phone, current_stock, new_stock)

    send_text(manager_phone, t(manager_phone, "request_approved_mgr", request_id=request_id, item_name=item_name, action=action, qty=qty, new_stock=new_stock))
    send_text(worker_phone, t(worker_phone, "request_approved_wkr", request_id=request_id, action=action, qty=qty, item_name=item_name, new_stock=new_stock))

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
        send_text(manager_phone, t(manager_phone, "low_stock_no_supplier", item_name=item_name, item_id=item_id, stock=new_stock, min_stock=min_stock))
        return

    # For JIT, just use the first supplier
    supplier = get_supplier(supplier_ids[0])
    if not supplier:
        return

    supplier_number = str(supplier["Contact_Number"]).strip().lstrip("+")
    supplier_name = supplier["Name"]
    reorder_text = f"Hi {supplier_name}, I'd like to reorder *{item_name}* (ID: {item_id}). Current stock is {new_stock}."
    wa_link = f"https://wa.me/{supplier_number}?text={requests.utils.quote(reorder_text)}"

    send_text(manager_phone, t(manager_phone, "low_stock_alert", item_name=item_name, item_id=item_id, stock=new_stock, min_stock=min_stock, supplier_name=supplier_name, wa_link=wa_link))


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
            body=f"🤖 {reply}\n\n{t(phone, 'ai_confirm_prompt')}",
            buttons=[
                {"id": "ai_confirm_yes", "title": t(phone, "btn_yes")},
                {"id": "ai_confirm_no", "title": t(phone, "btn_cancel")}
            ]
        )
            
    except Exception as e:
        logger.error(f"AI Parse Error: {e}\nRaw output: {actions_json}")
        send_text(phone, t(phone, "ai_confused"))

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
                    results.append(t(phone, "create_mgr_only"))
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
                results.append(t(phone, "created_item", name=name, item_id=new_id, qty=qty))
                continue

            if action in ["Add", "Deduct"]:
                item_id = act.get("item_id")
                item = get_inventory_item(item_id)
                if not item:
                    results.append(t(phone, "item_not_found", item_id=item_id))
                    continue
                    
                if role == "worker":
                    req_id = create_approval(phone, item_id, action, qty)
                    results.append(t(phone, "requested_action", action=action, qty=qty, item_name=item['Item_Name']))
                    manager_phone = get_manager_phone()
                    if manager_phone:
                        body = t(manager_phone, "new_request_header", req_id=req_id, phone=phone, item_name=item['Item_Name'], action=action, qty=qty)
                        send_button_message(
                            to=manager_phone, body=body,
                            buttons=[
                                {"id": f"approve_{req_id}", "title": t(manager_phone, "btn_approve")},
                                {"id": f"reject_{req_id}", "title": t(manager_phone, "btn_reject")},
                            ]
                        )
                else:
                    current_stock = int(item["Current_Stock"])
                    new_stock = current_stock + qty if action == "Add" else current_stock - qty
                    update_inventory_stock(item_id, new_stock)
                    log_history(item_id, item["Item_Name"], action, qty, phone, current_stock, new_stock)
                    results.append(t(phone, "action_done", action=action, qty=qty, item_name=item['Item_Name'], new_stock=new_stock))
                    
        if results:
            send_text(phone, t(phone, "ai_summary") + "\n".join(results))
    except Exception as e:
        logger.error(f"AI Execute Error: {e}")
        send_text(phone, t(phone, "ai_error"))

# ---------------------------------------------------------------------------
# Flask routes
# ---------------------------------------------------------------------------

@app.route("/", methods=["GET"])
def index():
    """Root endpoint for health checks and status."""
    return jsonify({"status": "online", "service": "WhatsApp Inventory Bot"}), 200


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
                            send_text(phone, t(phone, "ai_disabled"))
                            continue
                            
                        send_text(phone, t(phone, "ai_processing_media", media_type=msg_type))
                        media_id = msg[msg_type]["id"]
                        file_path, mime_type = _download_whatsapp_media(media_id)
                        if file_path:
                            ai_resp = process_with_gemini(phone, file_path, mime_type)
                            propose_ai_actions(phone, ai_resp)
                        else:
                            send_text(phone, t(phone, "ai_download_fail"))
                            
                    else:
                        # Pass unsupported types to AI to handle naturally
                        if GEMINI_API_KEY:
                            send_text(phone, t(phone, "ai_thinking"))
                            ai_resp = process_with_gemini(phone, None, None, t(phone, "unsupported_msg", msg_type=msg_type))
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
