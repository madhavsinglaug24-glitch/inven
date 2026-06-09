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

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")


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

def create_approval(worker_phone: str, item_id: str, action: str, qty: int, request_id: str = None) -> str:
    """Insert a new row in the Approvals sheet and return the Request_ID."""
    ws = _worksheet("Approvals")
    if not request_id:
        request_id = f"REQ-{uuid.uuid4().hex[:8].upper()}"
    ws.append_row([request_id, worker_phone, item_id, action, qty, "Pending"])
    return request_id


def get_approvals(request_id: str) -> list[dict]:
    """Return all Approvals rows by Request_ID."""
    ws = _worksheet("Approvals")
    matches = []
    for row in ws.get_all_records():
        if str(row.get("Request_ID", "")).strip() == request_id.strip():
            matches.append(row)
    return matches


def update_approval_status(request_id: str, new_status: str):
    """Set the Status column for a given Request_ID."""
    ws = _worksheet("Approvals")
    records = ws.get_all_records()
    headers = ws.row_values(1)
    col = headers.index("Status") + 1
    for idx, row in enumerate(records, start=2):
        if str(row.get("Request_ID", "")).strip() == request_id.strip():
            ws.update_cell(idx, col, new_status)

# ---- History --------------------------------------------------------------

def log_history(item_id: str, item_name: str, action: str, qty: int, editor_phone: str, previous_stock: int, new_stock: int, contact_type: str = "", contact_name: str = "", comment: str = "", txn_id: str = None):
    """Log an inventory change to the History tab."""
    try:
        ws = _worksheet("History")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not txn_id:
            txn_id = f"TXN-{uuid.uuid4().hex[:6].upper()}"
        ws.append_row([timestamp, item_id, item_name, action, qty, editor_phone, previous_stock, new_stock, contact_type, contact_name, comment, txn_id])
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

def log_ledger(ledger_type: str, amount: float, name: str, comment: str, user_phone: str, txn_id: str = None):
    """Log a ledger transaction to the Ledger tab."""
    try:
        ws = _worksheet("Ledger")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not txn_id:
            txn_id = f"TXN-{uuid.uuid4().hex[:6].upper()}"
        ws.append_row([timestamp, ledger_type, amount, name, comment, user_phone, txn_id])
    except Exception as e:
        logger.error(f"Failed to log ledger: {e}")

def get_recent_ledger(limit=5) -> list[dict]:
    """Get the most recent ledger records."""
    try:
        ws = _worksheet("Ledger")
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
# Core conversation-state tracker (Persistent, keyed by phone number)
# ---------------------------------------------------------------------------
import time

SESSION_DIR = "sessions"
if not os.path.exists(SESSION_DIR):
    os.makedirs(SESSION_DIR)

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

def handle_message(phone: str, text: str):
    """Route a plain-text message based on the sender's role."""
    text_lower = text.strip().lower()

    # Language switching (available to everyone, even unregistered)
    if text_lower.startswith("lang"):
        parts = text_lower.split()
        if len(parts) == 2:
            user_lang[phone] = parts[1].lower()
            _save_user_prefs(user_lang)
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
    
    session = get_session(phone)
    if session and session.get("state") == "editing_approval":
        if text_lower == "cancel":
            reset_session(phone)
            send_text(phone, "❌ Edit cancelled.")
            return
        edit_req_id = session.get("edit_req_id")
        response_text = process_with_groq(phone, file_path=None, mime_type=None, user_text=text, edit_req_id=edit_req_id)
        propose_ai_actions(phone, response_text)
        return

    # Explicit greeting
    if text_lower in ["hi", "hello", "hey", "start", "menu"]:
        if role == "manager":
            send_button_message(
                to=phone,
                body=f"👋 Hello {name}!\nWhich module would you like to use today?",
                buttons=[
                    {"id": "main_btn_inv", "title": "📦 Inventory"},
                    {"id": "main_btn_ledger", "title": "📓 Ledger"}
                ]
            )
        else:
            session = get_session(phone)
            session["module"] = "inventory"
            save_session(phone, session)
            send_button_message(
                to=phone,
                body=f"👋 Hello {name}! You are logged in as a *Worker*.\nYou can send me images of receipts, or choose an action below to enter manually:",
                buttons=[
                    {"id": "ai_btn_Restock", "title": "📥 Restock"},
                    {"id": "ai_btn_Consume", "title": "📤 Consume"},
                    {"id": "ai_btn_Stock", "title": "📦 Check Stock"}
                ]
            )
        return

    # Handle Top-level modules
    if text_lower == "main_btn_inv":
        session = get_session(phone)
        session["module"] = "inventory"
        save_session(phone, session)
        if role == "manager":
            send_list_message(
                to=phone,
                header="Manager Menu",
                body=f"📦 *Inventory Mode*\nYou can send me images of receipts, or choose an action below to enter manually:",
                button_text="Menu",
                sections=[{"title": "Actions", "rows": [
                    {"id": "ai_btn_Restock", "title": "📥 Restock"},
                    {"id": "ai_btn_Consume", "title": "📤 Consume"},
                    {"id": "ai_btn_Stock", "title": "📦 Check Stock"},
                    {"id": "ai_btn_Pending", "title": "⏳ Pending"},
                    {"id": "ai_btn_History", "title": "📜 History"}
                ]}]
            )
        else:
            send_button_message(
                to=phone,
                body=f"📦 *Inventory Mode*\nYou can send me images of receipts, or choose an action below to enter manually:",
                buttons=[
                    {"id": "ai_btn_Restock", "title": "📥 Restock"},
                    {"id": "ai_btn_Consume", "title": "📤 Consume"},
                    {"id": "ai_btn_Stock", "title": "📦 Check Stock"}
                ]
            )
        return

    if text_lower == "main_btn_ledger":
        session = get_session(phone)
        session["module"] = "ledger"
        save_session(phone, session)
        send_button_message(
            to=phone,
            body=f"📓 *Ledger Mode*\nWhat would you like to do?",
            buttons=[
                {"id": "ai_btn_Log_Transaction", "title": "📝 Log Transaction"},
                {"id": "ai_btn_Monthly_Summary", "title": "📊 Monthly Summary"},
                {"id": "ai_btn_Ledger_History", "title": "📜 Ledger History"}
            ]
        )
        return

    # Admin tool to mass-capitalize
    if text_lower == "admin fix names" and role == "manager":
        send_text(phone, "⏳ Capitalizing all existing inventory names...")
        try:
            ws = _worksheet("Inventory")
            records = ws.get_all_records()
            updated = 0
            for idx, row in enumerate(records):
                current_name = str(row.get("Item_Name", ""))
                if current_name:
                    new_name = current_name.title()
                    if new_name != current_name:
                        # idx=0 is row 2 in sheets (header is row 1)
                        ws.update_cell(idx + 2, 2, new_name)
                        updated += 1
            send_text(phone, f"✅ Fixed {updated} items in the database!")
        except Exception as e:
            send_text(phone, f"❌ Error fixing names: {e}")
        return

    # Only keep the pending check for managers
    if "pending" in text_lower and role == "manager":
        _send_pending_approvals(phone)
        return
        
    if "ledger history" in text_lower:
        _send_ledger_history(phone)
        return

    if "monthly summary" in text_lower:
        _send_monthly_summary(phone)
        return

    if "history" in text_lower and role == "manager":
        if session.get("module") == "ledger":
            _send_ledger_history(phone)
            return
        send_button_message(
            to=phone,
            body="How would you like to view the History?",
            buttons=[
                {"id": "btn_hist_chat", "title": "💬 Chat View"},
                {"id": "btn_hist_excel", "title": "📊 Excel View"}
            ]
        )
        return
        
    if "stock" in text_lower or "inventory" in text_lower:
        _send_inventory_list(phone)
        return

    # Fallback to AI Processing for everything
    if GROQ_API_KEY:
        # send_text(phone, t(phone, "ai_thinking"))
        ai_resp = process_with_groq(phone, None, None, text)
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

    grouped = {}
    for r in pending:
        req_id = r["Request_ID"]
        if req_id not in grouped:
            grouped[req_id] = []
        grouped[req_id].append(r)

    for req_id, items in grouped.items():
        worker = items[0]["Worker_Number"]
        
        items_str = ""
        for r in items:
            item = get_inventory_item(r["Item_ID"])
            item_name = item["Item_Name"] if item else r["Item_ID"]
            items_str += f"\n• {r['Action']} {r['Quantity']}x {item_name}"
            
        body = f"⏳ *Pending Request*: {req_id}\n👤 *Worker*: {worker}\n{items_str}\n\nPlease review."
        
        send_button_message(
            to=phone,
            body=body,
            buttons=[
                {"id": f"approve_{req_id}", "title": t(phone, "btn_approve")},
                {"id": f"reject_{req_id}", "title": t(phone, "btn_reject")},
                {"id": f"edit_{req_id}", "title": "✏️ Edit"},
            ],
        )

def _send_history_list(phone: str):
    history = get_recent_history(limit=15)
    if not history:
        send_text(phone, "📜 No recent history found.")
        return
        
    msg = "📜 *Recent History*\n\n"
    for h in history:
        date_str = str(h.get('Timestamp', ''))[:16]
        comment_str = f"\n  💬 {h.get('Comment')}" if h.get('Comment') else ""
        contact_str = f"\n  👤 {h.get('Contact_Type', 'Contact')}: {h.get('Contact_Name')}" if h.get('Contact_Name') else ""
        msg += f"• {date_str} ({h.get('User_Phone', '')[-4:]})\n  {h.get('Action', '')} {h.get('Quantity', '')}x {h.get('Item_Name', '')} [ID: {h.get('Txn_ID', '')}]{contact_str}{comment_str}\n\n"
    
    send_text(phone, msg.strip())
    
def _send_history_excel(phone: str):
    sheet_url = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/edit"
    send_text(phone, f"📊 *Excel / Spreadsheet View*\n\nYou can view the full, unlimited history and usage changes directly in the Google Sheet database here:\n{sheet_url}")
    
def _send_inventory_list(phone: str):
    user = get_user(phone)
    role = str(user.get("Role", "worker")).strip().lower() if user else "worker"
    
    items = get_all_inventory()
    if not items:
        send_text(phone, "📦 Inventory is empty.")
        return
        
    msg = "📦 *Current Inventory*\n\n"
    for i in items:
        stock = i.get('Current_Stock', 0)
        name = i.get('Item_Name', 'Unknown')
        if role == "manager":
            price = i.get('Purchase_Price', 0)
            msg += f"• *{name}*: {stock} in stock (₹{price})\n"
        else:
            msg += f"• *{name}*: {stock} in stock\n"
            
    send_text(phone, msg.strip()[:4000])

def _send_monthly_summary(phone: str):
    from datetime import datetime
    now = datetime.now()
    current_month_str = now.strftime("%Y-%m")
    
    try:
        ws = _worksheet("Ledger")
        records = ws.get_all_records()
    except Exception as e:
        send_text(phone, f"❌ Failed to read Ledger: {e}")
        return
        
    total_credit = 0.0
    total_debit = 0.0
    total_cash = 0.0
    
    for r in records:
        date_str = str(r.get("Date", ""))
        if date_str.startswith(current_month_str):
            l_type = str(r.get("Type", "")).lower()
            try:
                amt = float(str(r.get("Amount", 0)).replace(',', ''))
            except:
                amt = 0.0
                
            if "credit" in l_type:
                total_credit += amt
            elif "debit" in l_type:
                total_debit += amt
            elif "cash" in l_type:
                total_cash += amt
                
    msg = f"📊 *Monthly Ledger Summary ({now.strftime('%B %Y')})*\n\n"
    msg += f"💵 Cash in Hand: ₹{total_cash:,.2f}\n"
    msg += f"📈 Total Credit: ₹{total_credit:,.2f}\n"
    msg += f"📉 Total Debit: ₹{total_debit:,.2f}\n"
    
    send_text(phone, msg)

def _send_ledger_history(phone: str):
    history = get_recent_ledger(limit=10)
    if not history:
        send_text(phone, "📜 No recent ledger history found.")
        return
        
    msg = "📜 *Recent Ledger History*\n\n"
    for h in history:
        date_str = str(h.get('Date', ''))[:16]
        comment_str = f"\n  💬 {h.get('Comment')}" if h.get('Comment') else ""
        msg += f"• {date_str} ({str(h.get('Logged_By', ''))[-4:]})\n  {h.get('Type', '')}: ₹{h.get('Amount', '')} for {h.get('Name', '')} [ID: {h.get('Txn_ID', '')}]{comment_str}\n\n"
    
    send_text(phone, msg.strip())


# ---------------------------------------------------------------------------
# Interactive message handler (button & list replies)
# ---------------------------------------------------------------------------

def handle_interactive(phone: str, interactive_data: dict):
    """Handle Interactive message replies (buttons & list selections)."""
    msg_type = interactive_data.get("type")

    if msg_type == "button_reply":
        button_id = interactive_data["button_reply"]["id"]
        if button_id.startswith("ai_btn_"):
            handle_message(phone, interactive_data["button_reply"]["title"])
        elif button_id.startswith("main_btn_"):
            handle_message(phone, button_id)
        else:
            _handle_button_reply(phone, button_id)
    elif msg_type == "list_reply":
        list_id = interactive_data["list_reply"]["id"]
        if list_id.startswith("ai_sel_"):
            item_id = list_id[7:]
            if item_id == "CREATE_NEW":
                handle_message(phone, "I want to create a new item instead.")
            else:
                handle_message(phone, f"I am referring to item ID: {item_id}")
        elif list_id.startswith("ai_btn_"):
            handle_message(phone, interactive_data["list_reply"]["title"])


def _handle_button_reply(phone: str, button_id: str):
    """Process Approve / Reject button clicks and AI confirmation."""
    if button_id == "ai_confirm_yes":
        session = get_session(phone)
        if session and session.get("state") == "awaiting_ai_confirm":
            actions = session.get("pending_actions", [])
            edit_req_id = session.get("edit_req_id")
            execute_ai_actions(phone, actions, edit_req_id=edit_req_id)
            reset_session(phone)
        else:
            send_text(phone, t(phone, "ai_expired"))
        return
        
    if button_id == "ai_confirm_no":
        session = get_session(phone)
        if session:
            session.pop("state", None)
            session.pop("pending_actions", None)
            history = session.get("history", [])
            history.append({"role": "user", "content": "I cancelled the action. Please ask me what I want to change."})
            session["history"] = history
            save_session(phone, session)
        send_text(phone, "❌ Action cancelled. What details would you like to change?")
        return

    user = get_user(phone)
    if not user or str(user.get("Role", "")).strip().lower() != "manager":
        send_text(phone, t(phone, "managers_only"))
        return

    if button_id == "btn_hist_chat":
        _send_history_list(phone)
        return
    if button_id == "btn_hist_excel":
        _send_history_excel(phone)
        return

    if button_id.startswith("approve_"):
        request_id = button_id.replace("approve_", "")
        _process_approval(phone, request_id, approved=True)

    elif button_id.startswith("reject_"):
        request_id = button_id.replace("reject_", "")
        _process_approval(phone, request_id, approved=False)

    elif button_id.startswith("edit_"):
        request_id = button_id.replace("edit_", "")
        approvals = get_approvals(request_id)
        if not approvals:
            send_text(phone, t(phone, "request_not_found", request_id=request_id))
            return
            
        session = get_session(phone)
        session["state"] = "editing_approval"
        session["edit_req_id"] = request_id
        save_session(phone, session)
        
        items_str = ""
        for approval in approvals:
            item = get_inventory_item(str(approval["Item_ID"]).strip())
            item_name = item["Item_Name"] if item else str(approval["Item_ID"])
            items_str += f"\n• {approval['Action']} {approval['Quantity']}x {item_name}"
            
        send_text(phone, f"✏️ You are editing Request *{request_id}*:{items_str}\n\nWhat would you like to change? (e.g. 'Change quantity to 20', 'Change supplier to XYZ').\nType *cancel* to abort.")


def _process_approval(manager_phone: str, request_id: str, approved: bool):
    """Approve or reject a pending request and update sheets accordingly."""
    approvals = get_approvals(request_id)
    if not approvals:
        send_text(manager_phone, t(manager_phone, "request_not_found", request_id=request_id))
        return

    if any(str(a.get("Status", "")).strip().lower() != "pending" for a in approvals):
        send_text(manager_phone, t(manager_phone, "request_already", request_id=request_id, status=approvals[0]['Status']))
        return

    worker_phone = str(approvals[0]["Worker_Number"]).strip()

    if not approved:
        update_approval_status(request_id, "Rejected")
        send_text(manager_phone, f"❌ Request {request_id} has been rejected.")
        send_text(worker_phone, f"❌ Your request {request_id} was rejected by the manager.")
        return

    # Approved — update inventory
    import uuid
    shared_txn_id = f"TXN-{uuid.uuid4().hex[:6].upper()}"
    
    for approval in approvals:
        item_id = str(approval["Item_ID"]).strip()
        action = str(approval["Action"]).strip()
        qty = int(approval["Quantity"])
        item = get_inventory_item(item_id)
        if item is None:
            continue
            
        current_stock = int(item["Current_Stock"])
        if action.lower() in ["add", "restock"]:
            new_stock = current_stock + qty
        else:
            new_stock = current_stock - qty

        update_inventory_stock(item_id, new_stock)
        log_history(item_id, item["Item_Name"], action, qty, worker_phone, current_stock, new_stock, txn_id=shared_txn_id)

        # JIT wholesaler trigger
        if action.lower() == "deduct" or action.lower() == "consume":
            min_stock = int(item.get("Min_Stock", 0))
            supplier_id = str(item.get("Supplier_ID", ""))
            _jit_check(manager_phone, item_id, item["Item_Name"], new_stock, min_stock, supplier_id)

    update_approval_status(request_id, "Approved")
    send_text(manager_phone, f"✅ Request {request_id} approved. Inventory updated.")
    send_text(worker_phone, f"✅ Your request {request_id} was approved by the manager!")


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

def process_with_groq(phone: str, file_path: str, mime_type: str, user_text: str = None, edit_req_id: str = None) -> str:
    """Send text, image, or audio to Gemini to converse or parse actions."""
    user = get_user(phone)
    role = str(user.get("Role", "worker")).strip().lower() if user else "worker"
    
    session = get_session(phone)
    module = session.get("module", "inventory")
    
    if module == "ledger":
        items_str = "[]"
        sup_str = "[]"
        try:
            history = get_recent_ledger(limit=20)
            hist_str = json.dumps(history)
        except:
            hist_str = "[]"
    else:
        items = get_all_inventory()
        if role == "manager":
            items_str = json.dumps([{"id": i["Item_ID"], "name": i["Item_Name"], "stock": i["Current_Stock"], "min": i.get("Min_Stock", 0), "price": i.get("Purchase_Price", 0), "sup_id": i.get("Supplier_ID", "")} for i in items])
        else:
            items_str = json.dumps([{"id": i["Item_ID"], "name": i["Item_Name"], "stock": i["Current_Stock"], "min": i.get("Min_Stock", 0), "sup_id": i.get("Supplier_ID", "")} for i in items])
        try:
            suppliers = _worksheet("Suppliers").get_all_records()
            sup_str = json.dumps([{"id": s["Supplier_ID"], "name": s["Name"]} for s in suppliers])
        except:
            sup_str = "[]"
            
        try:
            history = get_recent_history(limit=20)
            hist_str = json.dumps(history)
        except:
            hist_str = "[]"
        
    try:
        ledger_ws = _worksheet("Ledger")
        ledger_records = ledger_ws.get_all_records()
        ledger_contacts = list(set([str(r.get("Name", "")).strip() for r in ledger_records if str(r.get("Name", "")).strip()]))
        ledger_contacts_str = json.dumps(ledger_contacts)
    except:
        ledger_contacts_str = "[]"
    
    lang = user_lang.get(phone, DEFAULT_LANG)
    lang_map = {"en": "English", "hi": "Hindi", "pa": "Punjabi"}
    pref_lang = lang_map.get(lang, lang.capitalize())
    
    edit_instruction = ""
    if edit_req_id:
        approvals = get_approvals(edit_req_id)
        if approvals:
            items_str = "\n".join([f"- {a['Action']} {a['Quantity']}x {a['Item_ID']}" for a in approvals])
            edit_instruction = f"""
    === MANAGER EDITING MODE ===
    You are helping a manager edit a pending transaction request from a worker.
    Original Request Items:
    {items_str}
    
    The manager will tell you what to change. You MUST output the FINAL updated JSON action based on their changes as if you were creating it from scratch. Set "is_ready_to_execute" to true if the final details are clear.
    ============================
    """
    
    session = get_session(phone)
    module = session.get("module", "inventory")
    
    if module == "ledger":
        persona = "You are an AI Ledger and Accounting Assistant."
        module_goal = "Your goal is to record financial transactions into the Ledger (Cash in Hand, Credit, or Debit)."
        module_rules = f"""
    1. If the user provides an image of a bill or receipt, or says "Log Transaction", ask them if it's Cash in Hand, Credit, or Debit, and the amount/name.
    2. For every ledger entry, you need the Ledger Type (Cash in Hand, Credit, Debit), the Amount, and the Name of the person/company. A comment is optional.
    3. If any details are ambiguous (missing name, missing amount), politely ask the user for clarification in your reply. Do NOT guess.
    4. Output actions for Ledger format: [{{"action": "Ledger_Entry", "ledger_type": "Cash in Hand", "amount": 100, "name": "Person Name", "comment": "Optional comment"}}] (ledger_type must be Cash in Hand, Credit, or Debit)
    5. Do NOT try to modify inventory stock while in Ledger mode.
    6. STRICT LEDGER CONTACTS: The Existing Ledger Contacts are: {ledger_contacts_str}. If the user mentions a name that closely resembles an existing Ledger Contact, ask them to confirm if they meant that existing person. If they mention a completely new name, you MUST ask them to explicitly confirm if they want to log a transaction for a brand new person. If the name matches exactly, proceed to log it.
    7. If you are asking the user a multiple choice question (like "Cash, Credit, or Debit?"), you can provide up to 3 options by adding a "buttons" array: "buttons": ["Cash in Hand", "Credit", "Debit"].
    8. You MUST NOT set "is_ready_to_execute" to true UNTIL you have successfully gathered EVERY REQUIRED DETAIL (Ledger Type, Amount, and Name). If ANY detail is missing, set "is_ready_to_execute" to false and ask for it.
    9. SINGLE CONFIRMATION: NEVER ask the user "Are you sure?" or to confirm their action inside the chat. Once you have all the required details, immediately set "is_ready_to_execute" to true. The system will automatically handle the final confirmation with buttons.
        """
    else:
        persona = "You are an AI Inventory Assistant."
        module_goal = "Your goal is to gather information to execute an inventory update (Restock, Consume, or Create a new item), OR answer questions about the current stock, suppliers, or history."
        module_rules = f"""
    1. If the user provides an image of a bill or receipt, you MUST ask them to clarify if this is a "Restock" (adding new stock/purchase) or a "Consume" (removing stock/sale), unless the image explicitly makes it obvious.
    2. If any details are ambiguous (missing item name, missing quantity, unclear action), politely ask the user for clarification in your reply. Do NOT guess.
    3. If the user just asks a question (like "what is the history of ITEM-1" or "how much stock do we have"), just answer them in the `reply_to_user` field and leave `actions` empty!
    4. If you are asking the user a multiple choice question (like "Restock or Consume?" or "Yes or No?"), you can provide up to 10 options by adding a "buttons" array: "buttons": ["Restock", "Consume"]. DO NOT add a "buttons" array for open-ended questions where the user needs to type a name, number, or detail.
    5. When setting "is_ready_to_execute" to true, your `reply_to_user` MUST NOT say that the action is already completed or edited. Instead, say "I am ready to make this update."
    6. HALLUCINATION PREVENTION: You MUST NEVER invent or hallucinate an `item_id`. If the user asks to Restock or Consume an item that does NOT exactly match the provided `Current inventory` list, you must tell them it is not found.
    7. PERMISSION TO CREATE: You MUST NEVER use the "Create" action unless the user explicitly tells you to create a new item or you explicitly ask them "Would you like to create this as a new item?" and they say Yes.
    8. DUPLICATE PREVENTION: You MUST NEVER create an item that has the EXACT same name as an existing item in the inventory. If the user tries to create an item with a very similar name to existing items, or asks for an item that doesn't exist but similar ones do, you MUST tell them about the similar items first and ask if they meant one of those.
    9. REVERSALS & COMMENTS: If the user asks to reverse a transaction, find the `Txn_ID` in the Recent History and output action "Reverse" with the "transaction_id". Capture any optional comments the user makes into the "comment" field. Map names to "contact_name" and set "contact_type" to "Supplier" for purchases/restocks and "Customer" for sales/consumes.
    10. Output actions in format: [{{"action": "Restock", "item_id": "ITEM-X", "quantity": 10, "contact_type": "Supplier", "contact_name": "Name of contact", "comment": "Any extra notes", "transaction_id": "TXN-XXXX", "new_item_name": "New Item", "new_item_price": 0, "new_item_min_stock": 0}}] (action must be Restock, Consume, Create, or Reverse)
    11. You MUST NOT set "is_ready_to_execute" to true UNTIL you have successfully gathered EVERY REQUIRED DETAIL (Action type, Item ID, and Quantity). If ANY detail is missing, set "is_ready_to_execute" to false and ask for it.
    12. SINGLE CONFIRMATION: NEVER ask the user "Are you sure?" or to confirm their action inside the chat. Once you have all the required details, immediately set "is_ready_to_execute" to true. The system will automatically handle the final confirmation with buttons.
    
    If the user wants to update an item, or asks for data about an item, and the item name is ambiguous or has multiple exact or close matches in the inventory, DO NOT guess which one they mean and DO NOT give back data for a random match. Instead, set "is_ready_to_execute" to false and return up to 9 matching items in "options": [{{"id": "ITEM-X", "title": "Item Name"}}]. To help the user distinguish between exact duplicate names, append the ID to the title in the options array (e.g., "Cement (ITEM-1)").
        """

    prompt_context = f"""
    {persona} You must be EXTREMELY brief, concise, and tight in all your replies. Never use filler words.
    You MUST output your `reply_to_user` entirely in {pref_lang}.
    Current User Phone: {phone}
    User Role: {role}
    Active Module: {module}
    Current inventory: {items_str}
    Current suppliers: {sup_str}
    Recent History (last 20 changes): {hist_str}
    
    {module_goal}
    {edit_instruction}
    CRITICAL RULES:
    {module_rules}
    
    You MUST ALWAYS respond with a structured JSON object in EXACTLY this format (no markdown code blocks, just raw JSON):
    {{
      "reply_to_user": "A VERY SHORT, concise, and tight reply. Get straight to the point. Give just the important stuff. Use emojis.",
      "is_ready_to_execute": false,
      "actions": [],
      "options": [],
      "buttons": []
    }}
    """
    
    try:
        import groq
        import base64
        
        client = groq.Groq(api_key=os.environ.get("GROQ_API_KEY"))
        
        # Dynamically verify available models to avoid decommissioned ones
        models_data = client.models.list().data
        available_models = [m.id for m in models_data]
        
        if file_path:
            # We want to test vision models in priority order
            test_models = [
                "meta-llama/llama-4-scout-17b-16e-instruct",
                "llama-4-scout-17b-16e-instruct",
                "llama-3.2-11b-vision-instruct",
                "llama-3.2-90b-vision-instruct",
                "llama-3.2-11b-vision-preview",
                "llama-3.2-90b-vision-preview",
                "llama-3.2-11b-vision",
                "llama-3.2-90b-vision"
            ]
            test_models.extend([m for m in available_models if ("vision" in m.lower() or "scout" in m.lower()) and m not in test_models])
        else:
            test_models = [
                "llama-3.1-8b-instant",
                "llama-3.3-70b-versatile",
                "llama-3.1-70b-versatile"
            ]
            test_models.extend([m for m in available_models if "llama" in m and "vision" not in m and m not in test_models])
        
        session = get_session(phone)
        # History in OpenAI format
        chat_history = session.get("history", [{"role": "system", "content": prompt_context}])
        # Ensure system prompt is always updated
        if chat_history and chat_history[0]["role"] == "system":
            chat_history[0]["content"] = prompt_context
        else:
            chat_history.insert(0, {"role": "system", "content": prompt_context})

        if mime_type and "audio" in mime_type:
            # Groq supports audio transcription via Whisper!
            with open(file_path, "rb") as f:
                transcription = client.audio.transcriptions.create(
                    file=(file_path, f.read()),
                    model="whisper-large-v3-turbo",
                )
            user_part = f"The user sent a voice note. Voice Transcription: '{transcription.text}'. Treat this transcription EXACTLY as if the user explicitly typed this command or question to you."
            messages = chat_history + [{"role": "user", "content": user_part}]
        elif file_path:
            with open(file_path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode('utf-8')
            img_url = f"data:{mime_type};base64,{encoded}"
            
            content = []
            content.append({
                "type": "text", 
                "text": "Please carefully analyze the attached image (it is a bill, receipt, or handwritten note). Step 1: Read all the text/elements visible in the image. Step 2: List exactly what you found directly in your reply."
            })
            if user_text:
                content.append({"type": "text", "text": f"The user also added this caption: '{user_text}'"})
            content.append({
                "type": "image_url",
                "image_url": {"url": img_url}
            })
            messages = chat_history + [{"role": "user", "content": content}]
        else:
            messages = chat_history + [{"role": "user", "content": user_text or ""}]
            
        response = None
        last_error = None
        
        logger.info(f"Available Groq models: {available_models}")
        logger.info(f"Testing Groq models: {test_models}")
        
        for target_model in test_models:
            try:
                response = client.chat.completions.create(
                    model=target_model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.1
                )
                break
            except Exception as e:
                err_str = str(e)
                if "decommissioned" in err_str.lower() or "not found" in err_str.lower() or "does not exist" in err_str.lower():
                    logger.warning(f"Groq model {target_model} failed (decommissioned or not found), trying next...")
                    last_error = e
                    continue
                elif "rate_limit" in err_str.lower() or "429" in err_str:
                    logger.warning(f"Groq model {target_model} hit rate limit, trying next...")
                    last_error = e
                    continue
                else:
                    raise e
                    
        if not response:
            raise last_error or Exception("No active models available")
        
        ai_resp = response.choices[0].message.content
        
        # Save history (append the user message and assistant reply, up to last 10)
        if file_path and not ("audio" in mime_type):
            chat_history.append({"role": "user", "content": f"[User sent an image]{' with caption: ' + user_text if user_text else ''}"})
        else:
            chat_history.append(messages[-1])
            
        chat_history.append({"role": "assistant", "content": ai_resp})
        
        # Keep system prompt + last 10 messages
        session["history"] = [chat_history[0]] + chat_history[-10:]
        save_session(phone, session)
        
        if file_path:
            os.remove(file_path)
            
        return ai_resp
        
    except Exception as e:
        logger.error(f"Groq API Error: {e}")
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            
        err_str = str(e)
        if "rate_limit" in err_str.lower() or "429" in err_str:
            retry_s = "1 minute"
            try:
                if hasattr(e, 'response') and e.response is not None:
                    retry_val = e.response.headers.get("retry-after")
                    if retry_val:
                        retry_s = f"{retry_val} seconds"
            except Exception:
                pass
            user_msg = f"⏳ Wow, you guys are fast! I hit my AI rate limit. Please wait {retry_s} and try again."
        elif "decommissioned" in err_str.lower() or "not found" in err_str.lower():
            user_msg = "🛠️ The AI models I was using were just retired by Groq! Please tell my developer."
        else:
            # Elegant display of raw error
            user_msg = f"⚠️ *Groq AI Encountered an Error*\n\n_Type:_ `{type(e).__name__}`\n_Details:_ `{err_str}`"
            
        return json.dumps({"reply_to_user": user_msg, "is_ready_to_execute": False, "actions": []})

def propose_ai_actions(phone: str, actions_json: str):
    """Parse Gemini JSON. Send conversational reply and show buttons if ready."""
    try:
        import re
        match = re.search(r'\{.*\}', actions_json, re.DOTALL)
        if not match:
            raise ValueError(f"No JSON object found in response: {actions_json}")
            
        data = json.loads(match.group(0))
        
        reply = data.get("reply_to_user", "I didn't understand that.")
        ready = data.get("is_ready_to_execute", False)
        actions = data.get("actions", [])
        options = data.get("options", [])
        buttons = data.get("buttons", [])
        
        if options and not ready:
            valid_rows = []
            for opt in options:
                if isinstance(opt, dict) and "id" in opt and "title" in opt:
                    valid_rows.append({"id": f"ai_sel_{opt['id']}", "title": str(opt["title"])[:24]})
                elif isinstance(opt, str):
                    buttons.append(opt)
            
            if valid_rows:
                valid_rows = valid_rows[:9]
                valid_rows.append({"id": "ai_sel_CREATE_NEW", "title": "➕ Create New Item"})
                
                send_list_message(
                    to=phone,
                    header="Select Item",
                    body="🤖 " + reply,
                    button_text="Options",
                    sections=[{"title": "Matches", "rows": valid_rows}]
                )
                return
                
        if buttons and not ready:
            if len(buttons) <= 3:
                wa_buttons = [{"id": f"ai_btn_{str(b).replace(' ', '_')[:10]}", "title": str(b)[:20]} for b in buttons]
                send_button_message(to=phone, body="🤖 " + reply, buttons=wa_buttons)
                return
            else:
                rows = [{"id": f"ai_btn_{str(b).replace(' ', '_')[:10]}", "title": str(b)[:24]} for b in buttons[:10]]
                if rows:
                    send_list_message(
                        to=phone,
                        header="Select Option",
                        body="🤖 " + reply,
                        button_text="Options",
                        sections=[{"title": "Available Choices", "rows": rows}]
                    )
                    return
            
        if not ready or not actions:
            send_text(phone, "🤖 " + reply)
            return

        session = get_session(phone)
        session["state"] = "awaiting_ai_confirm"
        session["pending_actions"] = actions
        save_session(phone, session)
        
        changes_str = "\n*Proposed Changes:*"
        for act in actions:
            act_type = str(act.get("action", "")).capitalize()
            qty = act.get('quantity', 0)
            if act_type == "Create":
                changes_str += f"\n• Create: {str(act.get('new_item_name', 'Unknown')).title()} (Qty: {qty})"
            elif act_type == "Reverse":
                changes_str += f"\n• Reverse TXN: {act.get('transaction_id', '')}"
            elif act_type.lower() == "ledger_entry":
                l_type = act.get("ledger_type", "Entry")
                amt = act.get("amount", 0)
                name = act.get("name", act.get("contact_name", "Unknown"))
                changes_str += f"\n• {l_type}: ₹{amt} for {name}"
            else:
                item_id = act.get("item_id", "")
                item_obj = get_inventory_item(item_id)
                item_name = item_obj["Item_Name"] if item_obj else item_id
                changes_str += f"\n• {act_type}: {qty}x {item_name}"
        
        send_button_message(
            to=phone,
            body=f"🤖 {reply}\n{changes_str}\n\n{t(phone, 'ai_confirm_prompt')}",
            buttons=[
                {"id": "ai_confirm_yes", "title": t(phone, "btn_yes")},
                {"id": "ai_confirm_no", "title": t(phone, "btn_cancel")}
            ]
        )
            
    except Exception as e:
        logger.error(f"AI Parse Error: {e}\nRaw output: {actions_json}")
        err_msg = f"🛠️ Debug Error: {type(e).__name__} - {e}\nRaw: {str(actions_json)[:100]}"
        send_text(phone, err_msg)

def execute_ai_actions(phone: str, actions: list, edit_req_id: str = None):
    """Apply actions or create worker approvals."""
    user = get_user(phone)
    role = str(user.get("Role", "")).strip().lower() if user else "worker"
    
    log_phone = phone
    if edit_req_id:
        approvals = get_approvals(edit_req_id)
        if approvals:
            log_phone = str(approvals[0].get("Worker_Number", phone)).strip()
            
    try:
        results = []
        import uuid
        shared_txn_id = f"TXN-{uuid.uuid4().hex[:6].upper()}"
        shared_req_id = f"REQ-{uuid.uuid4().hex[:8].upper()}"
        worker_req_items = []
        
        for act in actions:
            action = act.get("action", "").capitalize()
            qty = int(act.get("quantity", 0))
            c_type = act.get("contact_type", "")
            c_name = act.get("contact_name", "")
            comment = act.get("comment", "")
            
            if action.lower() == "ledger_entry":
                ledger_type = str(act.get("ledger_type", "Unknown")).title()
                amount = float(act.get("amount", 0))
                name = str(act.get("name", act.get("contact_name", "Unknown"))).title()
                log_ledger(ledger_type, amount, name, comment, log_phone, txn_id=shared_txn_id)
                results.append(f"✅ Logged {ledger_type} of ₹{amount} for {name}.")
                continue

            if action == "Create":
                if role != "manager":
                    results.append(t(phone, "create_mgr_only"))
                    continue
                name = str(act.get("new_item_name", "Unknown Item")).title()
                price = int(act.get("new_item_price", 0))
                min_stock = int(act.get("new_item_min_stock", 0))
                
                ws = _worksheet("Inventory")
                records = ws.get_all_records()
                max_num = max([int(str(r.get("Item_ID", "ITEM-0")).replace("ITEM-", "")) for r in records if str(r.get("Item_ID", "")).startswith("ITEM-")] + [0])
                new_id = f"ITEM-{max_num + 1}"
                
                ws.append_row([new_id, name, qty, min_stock, price, ""])
                log_history(new_id, name, "Create", qty, log_phone, 0, qty, c_type, c_name, comment, txn_id=shared_txn_id)
                results.append(t(phone, "created_item", name=name, item_id=new_id, qty=qty))
                continue

            if action in ["Add", "Deduct", "Restock", "Consume"]:
                item_id = act.get("item_id")
                item = get_inventory_item(item_id)
                if not item:
                    results.append(t(phone, "item_not_found", item_id=item_id))
                    continue
                    
                if role == "worker" and not edit_req_id:
                    create_approval(phone, item_id, action, qty, request_id=shared_req_id)
                    results.append(t(phone, "requested_action", action=action, qty=qty, item_name=item['Item_Name']))
                    worker_req_items.append(f"• {action} {qty}x {item['Item_Name']}")
                else:
                    current_stock = int(item["Current_Stock"])
                    new_stock = current_stock + qty if action in ["Add", "Restock"] else current_stock - qty
                    update_inventory_stock(item_id, new_stock)
                    log_history(item_id, item["Item_Name"], action, qty, log_phone, current_stock, new_stock, c_type, c_name, comment, txn_id=shared_txn_id)
                    results.append(t(phone, "action_done", action=action, qty=qty, item_name=item['Item_Name'], new_stock=new_stock))
                    
            if action == "Changelanguage":
                new_lang = str(act.get("new_language", "")).lower()
                if new_lang:
                    user_lang[phone] = new_lang
                    _save_user_prefs(user_lang)
                    results.append(t(phone, "lang_switched"))
                continue

            if action == "Reverse":
                if role != "manager":
                    results.append("🔒 Only managers can reverse transactions.")
                    continue
                txn_id = act.get("transaction_id", "")
                history = get_recent_history(limit=100)
                target_txns = [h for h in history if str(h.get("Txn_ID", "")) == txn_id]
                if not target_txns:
                    results.append(f"🔎 Transaction {txn_id} not found in recent history.")
                    continue
                
                for target_txn in target_txns:
                    item_id = target_txn["Item_ID"]
                    item = get_inventory_item(item_id)
                    if not item:
                        results.append(f"🔎 Original item {item_id} no longer exists.")
                        continue
                        
                    orig_action = target_txn["Action"].capitalize()
                    orig_qty = int(target_txn["Quantity"])
                    
                    current_stock = int(item["Current_Stock"])
                    if orig_action in ["Add", "Restock", "Create"]:
                        new_stock = current_stock - orig_qty
                    else:
                        new_stock = current_stock + orig_qty
                        
                    update_inventory_stock(item_id, new_stock)
                    log_history(item_id, item["Item_Name"], f"Reversed {txn_id}", orig_qty, phone, current_stock, new_stock, c_type, c_name, f"Reversal of {orig_action}. {comment}", txn_id=shared_txn_id)
                    results.append(f"✅ Reversed {txn_id} ({orig_action} {orig_qty}x {item['Item_Name']}). New stock: {new_stock}")

        # Post-loop logic for worker requests
        if worker_req_items:
            manager_phone = get_manager_phone()
            if manager_phone:
                items_str = "\n".join(worker_req_items)
                body = f"⏳ *Pending Multi-Item Request*: {shared_req_id}\n👤 *Worker*: {phone}\n{items_str}\n\nPlease review."
                send_button_message(
                    to=manager_phone, body=body,
                    buttons=[
                        {"id": f"approve_{shared_req_id}", "title": t(manager_phone, "btn_approve")},
                        {"id": f"reject_{shared_req_id}", "title": t(manager_phone, "btn_reject")},
                        {"id": f"edit_{shared_req_id}", "title": "✏️ Edit"},
                    ]
                )
        
        # Post-loop logic for edits
        if edit_req_id:
            update_approval_status(edit_req_id, "Approved (Edited)")
                    
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

    def background_task(payload):
        try:
            for entry in payload.get("entry", []):
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
                            if not GROQ_API_KEY:
                                send_text(phone, t(phone, "ai_disabled"))
                                continue
                                
                            send_text(phone, t(phone, "ai_processing_media", media_type=msg_type))
                            media_id = msg[msg_type]["id"]
                            caption = msg[msg_type].get("caption", None)
                            file_path, mime_type = _download_whatsapp_media(media_id)
                            if file_path:
                                ai_resp = process_with_groq(phone, file_path, mime_type, caption)
                                propose_ai_actions(phone, ai_resp)
                            else:
                                send_text(phone, t(phone, "ai_download_fail"))
                                
                        else:
                            # Pass unsupported types to AI to handle naturally
                            if GROQ_API_KEY:
                                # send_text(phone, t(phone, "ai_thinking"))
                                ai_resp = process_with_groq(phone, None, None, t(phone, "unsupported_msg", msg_type=msg_type))
                                propose_ai_actions(phone, ai_resp)
        except Exception:
            logger.exception("Error processing webhook payload")

    # Run the heavy processing in a background thread to instantly return 200 OK to Meta
    import threading
    thread = threading.Thread(target=background_task, args=(data,))
    thread.start()

    # Always return 200 to Meta immediately to avoid retries
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
