import os
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials

load_dotenv(r"c:\Users\madha\Desktop\Co-pay\.env")

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

GOOGLE_SHEET_ID = os.environ["GOOGLE_SHEET_ID"]
GOOGLE_CREDENTIALS_FILE = os.environ.get("GOOGLE_CREDENTIALS_FILE", r"c:\Users\madha\Desktop\Co-pay\credentials.json")
if not os.path.isabs(GOOGLE_CREDENTIALS_FILE):
    GOOGLE_CREDENTIALS_FILE = os.path.join(r"c:\Users\madha\Desktop\Co-pay", GOOGLE_CREDENTIALS_FILE)

creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDENTIALS_FILE, SCOPES)
client = gspread.authorize(creds)
sheet = client.open_by_key(GOOGLE_SHEET_ID)

try:
    ws = sheet.worksheet("History")
    print("History tab already exists.")
except gspread.exceptions.WorksheetNotFound:
    ws = sheet.add_worksheet(title="History", rows=1000, cols=10)
    ws.update(values=[["Timestamp", "Item_ID", "Item_Name", "Action", "Quantity", "Editor_Phone", "Previous_Stock", "New_Stock"]], range_name="A1:H1")
    print("Created History tab successfully.")
