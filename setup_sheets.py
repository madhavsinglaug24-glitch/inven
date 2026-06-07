"""
One-time setup script: creates the required tabs and sample data
in the Google Sheet for the WhatsApp Inventory Chatbot.
"""

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
import os
import sys

# Fix Windows console encoding
sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

GOOGLE_SHEET_ID = os.environ["GOOGLE_SHEET_ID"]
GOOGLE_CREDENTIALS_FILE = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json")

creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDENTIALS_FILE, SCOPES)
client = gspread.authorize(creds)
sheet = client.open_by_key(GOOGLE_SHEET_ID)

# ---- Helper: create or get worksheet ------------------------------------
def get_or_create_ws(name, rows=100, cols=20):
    try:
        ws = sheet.worksheet(name)
        print(f"  Tab '{name}' already exists - clearing it.")
        ws.clear()
        return ws
    except gspread.exceptions.WorksheetNotFound:
        ws = sheet.add_worksheet(title=name, rows=rows, cols=cols)
        print(f"  Tab '{name}' created.")
        return ws


# ---- 1. Inventory --------------------------------------------------------
print("\n[1/4] Setting up Inventory tab...")
ws = get_or_create_ws("Inventory")
ws.update(values=[["Item_ID", "Item_Name", "Current_Stock", "Min_Stock", "Purchase_Price", "Supplier_ID"]], range_name="A1:F1")
ws.update(values=[
    ["ITEM-1", "Cement (50kg Bag)",  100, 20, 350,  "SUP-1"],
    ["ITEM-2", "Steel Rod (12mm)",    50, 10, 1200, "SUP-2"],
    ["ITEM-3", "Bricks (1000 pcs)",  500, 100, 8000, "SUP-1"],
    ["ITEM-4", "Sand (per ton)",      30,  5, 1500, "SUP-3"],
], range_name="A2:F5")
print("  [OK] Inventory tab ready with 4 sample items.")

# ---- 2. Users -----------------------------------------------------------
print("\n[2/4] Setting up Users tab...")
ws = get_or_create_ws("Users")
ws.update(values=[["Phone_Number", "Name", "Role"]], range_name="A1:C1")
ws.update(values=[
    ["919876543210", "Rahul",  "Worker"],
    ["919988776655", "Priya",  "Manager"],
], range_name="A2:C3")
print("  [OK] Users tab ready with sample Worker & Manager.")
print("  [!!] IMPORTANT: Replace phone numbers with YOUR actual numbers!")

# ---- 3. Suppliers --------------------------------------------------------
print("\n[3/4] Setting up Suppliers tab...")
ws = get_or_create_ws("Suppliers")
ws.update(values=[["Supplier_ID", "Name", "Contact_Number"]], range_name="A1:C1")
ws.update(values=[
    ["SUP-1", "ABC Building Materials", "919123456789"],
    ["SUP-2", "Steel Corp India",       "919234567890"],
    ["SUP-3", "River Sand Traders",     "919345678901"],
], range_name="A2:C4")
print("  [OK] Suppliers tab ready with 3 sample suppliers.")

# ---- 4. Approvals -------------------------------------------------------
print("\n[4/5] Setting up Approvals tab...")
ws = get_or_create_ws("Approvals")
ws.update(values=[["Request_ID", "Worker_Number", "Item_ID", "Action", "Quantity", "Status"]], range_name="A1:F1")
print("  [OK] Approvals tab ready (empty - bot will populate).")

# ---- 5. History ---------------------------------------------------------
print("\n[5/5] Setting up History tab...")
ws = get_or_create_ws("History")
ws.update(values=[["Timestamp", "Item_ID", "Item_Name", "Action", "Quantity", "Editor_Phone", "Previous_Stock", "New_Stock"]], range_name="A1:H1")
print("  [OK] History tab ready (empty - bot will populate).")

# ---- Clean up default Sheet1 if it exists --------------------------------
try:
    default = sheet.worksheet("Sheet1")
    sheet.del_worksheet(default)
    print("\n  Removed default 'Sheet1' tab.")
except Exception:
    pass

print("\n--- Google Sheet setup complete! ---")
print(f"Sheet URL: https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/edit")
print("\nDon't forget to update the phone numbers in the Users tab to your real numbers.")
