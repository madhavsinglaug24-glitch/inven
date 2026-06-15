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
import tempfile
from datetime import datetime, timezone

import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from flask_socketio import SocketIO
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix

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

DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "admin123")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")


logger = logging.getLogger(__name__)


# Per-user language preference (in-memory, keyed by phone)
USER_PREFS_FILE = "user_prefs.json"

def _load_user_prefs() -> dict:
    import json
    import os
    if os.path.exists(USER_PREFS_FILE):
        try:
            with open(USER_PREFS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _save_user_prefs(prefs: dict):
    import json
    import os
    try:
        with open(USER_PREFS_FILE, "w", encoding="utf-8") as f:
            json.dump(prefs, f)
    except Exception as e:
        logger.error(f"Failed to save user prefs: {e}")

user_lang: dict[str, str] = _load_user_prefs()

DEFAULT_LANG = "en"

STRINGS = {
    "en": {
        # ── General ──
        "not_registered":       "🚫 Not registered. Contact Manager.",
        "ai_thinking":          "✨ Processing...",
        "ai_disabled":          "🔌 AI offline (missing GROQ_API_KEY).",
        "ai_processing_media":  "🔍 Analyzing {media_type}...",
        "ai_download_fail":     "📥 Download failed. Resend?",
        "ai_expired":           "⏳ Action expired. Send again.",
        "ai_cancelled":         "🙅 Changes discarded.",
        "ai_confused":          "🤔 Didn't catch that. Rephrase?",
        "ai_error":             "⚡ System error. Try again.",
        "ai_summary":           "📊 *Summary:*\n",
        "ai_confirm_prompt":    "*Apply changes?*",
        "btn_yes":              "✅ Yes",
        "btn_cancel":           "❌ No",
        "unsupported_msg":      "(System note: User sent a '{msg_type}'. Tell them you only support text, voice, and images.)",

        # ── Manager / Approvals ──
        "managers_only":        "🔒 Managers only.",
        "no_pending":           "🎉 No pending requests.",
        "request_not_found":    "🔎 Request *{request_id}* not found.",
        "request_already":      "ℹ️ Request *{request_id}* already *{status}*.",
        "request_rejected_mgr": "✖️ Req *{request_id}* — *Rejected*",
        "request_rejected_wkr": "✖️ Req *{request_id}* ({action} {qty}× {item_name}) *declined*.",
        "item_missing":         "🔎 Item *{item_id}* not found.",
        "stock_insufficient":   "📉 Can't deduct {qty} — only *{stock}* left.",
        "request_approved_mgr": "✅ Req *{request_id}* — *Approved*\n📦 {item_name}\n🔄 {action} {qty}\n📊 Stock: {new_stock}",
        "request_approved_wkr": "✅ Req *{request_id}* ({action} {qty}× {item_name}) *approved*.\n📊 Stock: {new_stock}",
        "pending_header":       "📋 *Req {request_id}*\n👤 {worker}\n📦 {item_name}\n🔄 {action} {qty}",
        "btn_approve":          "✅ Approve",
        "btn_reject":           "❌ Reject",
        "new_request_header":   "📬 *New Req {req_id}*\n👤 {phone}\n📦 {item_name}\n🔄 {action} {qty}",

        # ── JIT / Low Stock ──
        "low_stock_no_supplier":"⚡ *Low Stock!*\n📦 {item_name}\n📊 Stock: {stock} (Min: {min_stock})\n⚠️ No supplier.",
        "low_stock_alert":      "🚨 *Low Stock!*\n📦 {item_name}\n📊 {stock}/{min_stock}\n🏭 {supplier_name}\n📲 Reorder:\n{wa_link}",

        # ── AI Actions ──
        "create_mgr_only":      "🔒 Managers only.",
        "created_item":         "✅ Created *{name}* ({item_id}), Stock: {qty}",
        "item_not_found":       "🔎 Item `{item_id}` not found.",
        "requested_action":     "📩 Sent: {action} {qty}× *{item_name}*",
        "action_done":          "✅ {action} {qty}× *{item_name}* → Stock: {new_stock}",

        # ── Language ──
        "lang_switched":        "🌐 Language set to *English* 🇬🇧",
        "lang_help":            "🌐 *Switch language:*\nType one of:\n• `lang en` — English 🇬🇧\n• `lang hi` — हिन्दी 🇮🇳\n• `lang pa` — ਪੰਜਾਬੀ 🇮🇳",
    },
    "hi": {
        # ── General ──
        "not_registered":       "🚫 लगता है आप अभी सिस्टम में नहीं हैं — सेटअप के लिए अपने मैनेजर से संपर्क करें।",
        "ai_thinking":          "✨ प्रोसेस हो रहा है…",
        "ai_disabled":          "🔌 AI अभी ऑफ़लाइन है। एडमिन को GROQ_API_KEY सेट करना होगा।",
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
        "ai_disabled":          "🔌 AI ਹੁਣ ਆਫ਼ਲਾਈਨ ਹੈ। ਐਡਮਿਨ ਨੂੰ GROQ_API_KEY ਸੈੱਟ ਕਰਨੀ ਪਵੇਗੀ।",
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

TRANSLATION_CACHE_FILE = "translation_cache.json"

def _load_translation_cache() -> dict:
    import json
    import os
    if os.path.exists(TRANSLATION_CACHE_FILE):
        try:
            with open(TRANSLATION_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _save_translation_cache(cache: dict):
    import json
    import os
    try:
        with open(TRANSLATION_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f)
    except Exception as e:
        logger.error(f"Failed to save translation cache: {e}")

_translation_cache = _load_translation_cache()

def t(phone: str, key: str, **kwargs) -> str:
    """Get a translated string for the user's preferred language."""
    lang = user_lang.get(phone, DEFAULT_LANG)
    
    # Fast path if natively supported
    if lang in STRINGS and key in STRINGS[lang]:
        template = STRINGS[lang][key]
    else:
        english_template = STRINGS[DEFAULT_LANG].get(key, key)
        if lang == DEFAULT_LANG:
            template = english_template
        else:
            cache_key = f"{lang}_{key}"
            if cache_key in _translation_cache:
                template = _translation_cache[cache_key]
            else:
                # Need to translate
                try:
                    import requests
                    headers = {
                        "Authorization": f"Bearer {GROQ_API_KEY}",
                        "Content-Type": "application/json"
                    }
                    data = {
                        "model": "llama3-8b-8192",
                        "messages": [
                            {"role": "system", "content": f"Translate the following English text to {lang.capitalize()}. Do not add any quotes, extra text, or explanations. Just output the translation. Keep formatting markers like {{key}} EXACTLY the same."},
                            {"role": "user", "content": english_template}
                        ],
                        "temperature": 0.0,
                        "max_tokens": 100
                    }
                    resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=data, timeout=5)
                    translation = resp.json()["choices"][0]["message"]["content"].strip()
                    _translation_cache[cache_key] = translation
                    _save_translation_cache(_translation_cache)
                    template = translation
                except Exception as e:
                    logger.error(f"Translation failed: {e}")
                    template = english_template

    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return template


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
            default_user = os.environ.get("ADMIN_USERNAME", "admin")
            default_pass = os.environ.get("DASHBOARD_PASSWORD", "admin123")
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


# ---- Users ----------------------------------------------------------------

def get_user(phone: str) -> dict | None:
    """Look up a user by phone number from DB. Returns dict with keys
    Phone_Number, Name, Role or None."""
    phone_clean = phone.strip().lstrip("+")
    try:
        with get_db_connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE phone_number = ?", (phone_clean,)).fetchone()
            if row:
                return {
                    "Phone_Number": row["phone_number"],
                    "Name": row["name"],
                    "Role": row["role"]
                }
    except Exception as e:
        logger.error(f"Error querying user {phone}: {e}")
    return None


def get_manager_phone() -> str | None:
    """Return the first Manager phone number found in the Users table."""
    try:
        with get_db_connection() as conn:
            row = conn.execute("SELECT phone_number FROM users WHERE lower(role) = 'manager' LIMIT 1").fetchone()
            if row:
                return row["phone_number"]
    except Exception as e:
        logger.error(f"Error querying manager phone: {e}")
    return None


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


# ---- Approvals ------------------------------------------------------------

def create_approval(worker_phone: str, item_id: str, action: str, qty: int, request_id: str = None) -> str:
    """Insert a new row in the Approvals table and return the Request_ID."""
    if not request_id:
        request_id = f"REQ-{uuid.uuid4().hex[:8].upper()}"
    try:
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO approvals (request_id, worker_number, item_id, action, quantity, status) VALUES (?, ?, ?, ?, ?, ?)",
                (request_id, str(worker_phone).strip().lstrip("+"), str(item_id).strip(), action, qty, "Pending")
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Error creating approval {request_id}: {e}")
    return request_id


def get_approvals(request_id: str) -> list[dict]:
    """Return all Approvals rows by Request_ID."""
    try:
        with get_db_connection() as conn:
            rows = conn.execute("SELECT * FROM approvals WHERE request_id = ?", (str(request_id).strip(),)).fetchall()
            return [{
                "Request_ID": r["request_id"],
                "Worker_Number": r["worker_number"],
                "Item_ID": r["item_id"],
                "Action": r["action"],
                "Quantity": r["quantity"],
                "Status": r["status"]
            } for r in rows]
    except Exception as e:
        logger.error(f"Error querying approvals {request_id}: {e}")
        return []


def update_approval_status(request_id: str, new_status: str):
    """Set the Status column for a given Request_ID."""
    try:
        with get_db_connection() as conn:
            conn.execute("UPDATE approvals SET status = ? WHERE request_id = ?", (new_status, str(request_id).strip()))
            conn.commit()
    except Exception as e:
        logger.error(f"Error updating approval status {request_id}: {e}")


# ---- History --------------------------------------------------------------

def log_history(item_id: str, item_name: str, action: str, qty: int, editor_phone: str, previous_stock: int, new_stock: int, contact_type: str = "", contact_name: str = "", comment: str = "", txn_id: str = None, bill_no: str = ""):
    """Log an inventory change to the History tab."""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not txn_id:
            txn_id = f"TXN-{uuid.uuid4().hex[:6].upper()}"
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO history (timestamp, item_id, item_name, action, quantity, user_phone, previous_stock, new_stock, contact_type, contact_name, comment, txn_id, bill_no) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (timestamp, item_id, item_name, action, qty, str(editor_phone).strip().lstrip("+"), previous_stock, new_stock, contact_type, contact_name, comment, txn_id, bill_no)
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to log history: {e}")

def get_recent_history(limit=5) -> list[dict]:
    """Get the most recent history records."""
    try:
        with get_db_connection() as conn:
            rows = conn.execute("SELECT * FROM history ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            return [{
                "Timestamp": r["timestamp"],
                "Item_ID": r["item_id"],
                "Item_Name": r["item_name"],
                "Action": r["action"],
                "Quantity": r["quantity"],
                "User_Phone": r["user_phone"],
                "Previous_Stock": r["previous_stock"],
                "New_Stock": r["new_stock"],
                "Contact_Type": r["contact_type"],
                "Contact_Name": r["contact_name"],
                "Comment": r["comment"],
                "Txn_ID": r["txn_id"],
                "Bill_No": r["bill_no"]
            } for r in rows]
    except Exception as e:
        logger.error(f"Failed to get recent history: {e}")
        return []

def log_ledger(ledger_type: str, amount: float, name: str, comment: str, user_phone: str, txn_id: str = None):
    """Log a ledger transaction to the Ledger tab."""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not txn_id:
            txn_id = f"TXN-{uuid.uuid4().hex[:6].upper()}"
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO ledger (timestamp, type, amount, name, comment, logged_by, txn_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (timestamp, ledger_type, amount, name, comment, str(user_phone).strip().lstrip("+"), txn_id)
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to log ledger: {e}")

def get_recent_ledger(limit=5) -> list[dict]:
    """Get the most recent ledger records."""
    try:
        with get_db_connection() as conn:
            rows = conn.execute("SELECT * FROM ledger ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            return [{
                "Date": r["timestamp"],
                "Type": r["type"],
                "Amount": r["amount"],
                "Name": r["name"],
                "Comment": r["comment"],
                "Logged_By": r["logged_by"],
                "Txn_ID": r["txn_id"]
            } for r in rows]
    except Exception as e:
        logger.error(f"Failed to get recent ledger: {e}")
        return []
    except Exception:
        return []

# ---------------------------------------------------------------------------
# WhatsApp message-sending helpers
# ---------------------------------------------------------------------------

def get_session(phone: str) -> dict:
    path = os.path.join(SESSION_DIR, f"{phone}.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                session = json.load(f)
                last_active = session.get("last_active", 0)
                # 20-minute expiry (1200 seconds)
                if time.time() - last_active > 1200:
                    os.remove(path)
                    return {}
                return session
        except Exception:
            return {}
    return {}

def save_session(phone: str, session: dict):
    path = os.path.join(SESSION_DIR, f"{phone}.json")
    session["last_active"] = time.time()
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(session, f)
        os.replace(tmp_path, path)
    except Exception as e:
        logger.error(f"Failed to save session for {phone}: {e}")

def reset_session(phone: str):
    path = os.path.join(SESSION_DIR, f"{phone}.json")
    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Incoming message routing
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
@app.route("/api/auth/login", methods=["POST"])
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
    
    return jsonify({"token": session_token, "username": username, "role": user["role"]}), 200





@app.route("/dashboard/login", methods=["POST"])
def dashboard_login():
    """Authenticate manager password and return a temporary API session token."""
    data = request.get_json() or {}
    password = data.get("password")
    if password == DASHBOARD_PASSWORD:
        token = f"dash-{uuid.uuid4().hex}"
        ACTIVE_SESSIONS[token] = datetime.now()
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
        total_items = len(inventory)
        low_stock_count = sum(1 for item in inventory if int(item.get("Current_Stock", 0)) < int(item.get("Min_Stock", 0)))
        
        with get_db_connection() as conn:
            
            current_month_str = datetime.now().strftime("%Y-%m")
            
            # Overall cash
            cash_row = conn.execute("SELECT SUM(amount) FROM ledger WHERE lower(type) LIKE '%cash%'").fetchone()
            total_cash = cash_row[0] if cash_row[0] is not None else 0.0
            
            # Monthly stats
            credit_row = conn.execute("SELECT SUM(amount) FROM ledger WHERE timestamp LIKE ? AND lower(type) LIKE '%credit%'", (f"{current_month_str}%",)).fetchone()
            debit_row = conn.execute("SELECT SUM(amount) FROM ledger WHERE timestamp LIKE ? AND lower(type) LIKE '%debit%'", (f"{current_month_str}%",)).fetchone()
            
            total_credit = credit_row[0] if credit_row[0] is not None else 0.0
            total_debit = debit_row[0] if debit_row[0] is not None else 0.0
            
        return jsonify({
            "total_items": total_items,
            "low_stock_count": low_stock_count,
            "cash_in_hand": total_cash,
            "month_credit": total_credit,
            "month_debit": total_debit
        }), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500



@app.route("/api/summary", methods=["GET"])
def api_summary():
    if not check_dashboard_auth():
        return jsonify({"message": "Unauthorized"}), 401
    try:
        with get_db_connection() as conn:
            # Income
            in_row = conn.execute("SELECT SUM(amount) FROM ledger WHERE type='Cash IN'").fetchone()
            income = in_row[0] if in_row[0] else 0.0
            
            # Expense
            out_row = conn.execute("SELECT SUM(amount) FROM ledger WHERE type='Cash OUT'").fetchone()
            expense = out_row[0] if out_row[0] else 0.0
            
            # Cash Balance
            cash_in_row = conn.execute("SELECT SUM(amount) FROM ledger WHERE type='Cash IN' AND (account IS NULL OR account='Cash')").fetchone()
            cash_in = cash_in_row[0] if cash_in_row[0] else 0.0
            cash_out_row = conn.execute("SELECT SUM(amount) FROM ledger WHERE type='Cash OUT' AND (account IS NULL OR account='Cash')").fetchone()
            cash_out = cash_out_row[0] if cash_out_row[0] else 0.0
            cash_balance = cash_in - cash_out
            
            # Bank Balance
            bank_in_row = conn.execute("SELECT SUM(amount) FROM ledger WHERE type='Cash IN' AND account='Bank'").fetchone()
            bank_in = bank_in_row[0] if bank_in_row[0] else 0.0
            bank_out_row = conn.execute("SELECT SUM(amount) FROM ledger WHERE type='Cash OUT' AND account='Bank'").fetchone()
            bank_out = bank_out_row[0] if bank_out_row[0] else 0.0
            bank_balance = bank_in - bank_out

            return jsonify({
                "income": income,
                "expense": expense,
                "balance": income - expense,
                "cash_balance": cash_balance,
                "bank_balance": bank_balance
            })
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route("/api/transactions", methods=["GET"])
def get_transactions():
    if not check_dashboard_auth():
        return jsonify({"message": "Unauthorized"}), 401
    try:
        limit = int(request.args.get('limit', 1000))
        with get_db_connection() as conn:
            query = '''
            SELECT id, txn_id, timestamp, name, amount, type, 
            SUM(CASE WHEN type LIKE '%IN%' THEN amount ELSE -amount END) OVER (ORDER BY timestamp ASC) as balance 
            FROM ledger 
            ORDER BY timestamp DESC LIMIT ?
            '''
            rows = conn.execute(query, (limit,)).fetchall()
            
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
                    'balance': r['balance'],
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
        amount = float(data.get("amount", 0))
        if amount <= 0: return jsonify({"error": "Amount must be strictly greater than 0"}), 400
        
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
        amount = float(data.get("amount", 0))
        if amount <= 0: return jsonify({"error": "Amount must be strictly greater than 0"}), 400
        
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
                conn.execute("DELETE FROM ledger WHERE id = ?", (id,))
                conn.commit()
                return jsonify({"success": True}), 200
            elif request.method == "PUT":
                data = request.json
                if 'amount' in data and float(data['amount']) < 0: return jsonify({"error": "Amount cannot be negative"}), 400
                updates = []
                params = []
                for field in ['amount', 'name', 'comment', 'timestamp', 'account']:
                    if field in data:
                        updates.append(f"{field} = ?")
                        params.append(data[field])
                if not updates: return jsonify({"error": "No updates provided"}), 400
                params.append(id)
                conn.execute(f"UPDATE ledger SET {', '.join(updates)} WHERE id = ?", params)
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
                    
                # Reverse ledger cash flow if there's a unit_price
                unit_price = row['unit_price'] if 'unit_price' in row.keys() else 0
                if unit_price and unit_price > 0:
                    amount = unit_price * qty
                    if action == 'RESTOCK':
                        conn.execute('INSERT INTO ledger (timestamp, type, amount, name, comment, logged_by, account) VALUES (?, ?, ?, ?, ?, ?, ?)',
                                     (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'Cash IN', amount, 'System', f'Reversal of Restock: {qty}x {row["item_name"]}', 'System', 'Cash'))
                    elif action == 'CONSUME':
                        conn.execute('INSERT INTO ledger (timestamp, type, amount, name, comment, logged_by, account) VALUES (?, ?, ?, ?, ?, ?, ?)',
                                     (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'Cash OUT', amount, 'System', f'Reversal of Sale: {qty}x {row["item_name"]}', 'System', 'Cash'))
                
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
                
            # Log single ledger entry for the total bulk transaction if there's money involved
            if total_price > 0:
                summary_text = ", ".join(names_for_ledger)
                if len(summary_text) > 50: summary_text = summary_text[:47] + "..."
                
                if action_type == 'restock':
                    conn.execute('INSERT INTO ledger (timestamp, type, amount, name, comment, logged_by) VALUES (?, ?, ?, ?, ?, ?)',
                                 (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'Cash OUT', total_price, supplier, f'Restock: {summary_text}', 'Web User'))
                elif action_type == 'consume':
                    conn.execute('INSERT INTO ledger (timestamp, type, amount, name, comment, logged_by) VALUES (?, ?, ?, ?, ?, ?)',
                                 (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'Cash IN', total_price, supplier, f'Sale: {summary_text}', 'Web User'))
            
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
            "model": "meta-llama/llama-3.2-11b-vision-instruct:free",
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
