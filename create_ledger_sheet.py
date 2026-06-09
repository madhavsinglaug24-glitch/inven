import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv

load_dotenv()

# Set up credentials and client
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds_file = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json")
creds = ServiceAccountCredentials.from_json_keyfile_name(creds_file, scope)
client = gspread.authorize(creds)

# Open the Google Sheet
SHEET_ID = os.environ.get("GOOGLE_SHEET_ID")
if not SHEET_ID:
    print("Error: GOOGLE_SHEET_ID not found in .env")
    exit(1)

print(f"Opening spreadsheet with ID: {SHEET_ID}")
try:
    spreadsheet = client.open_by_key(SHEET_ID)
except Exception as e:
    print(f"Failed to open spreadsheet: {e}")
    exit(1)

# Check if 'Ledger' exists, create if not
try:
    worksheet = spreadsheet.worksheet("Ledger")
    print("'Ledger' worksheet already exists.")
except gspread.exceptions.WorksheetNotFound:
    print("Creating 'Ledger' worksheet...")
    worksheet = spreadsheet.add_worksheet(title="Ledger", rows="1000", cols="20")
    
    # Add headers
    headers = ["Date", "Type", "Amount", "Name", "Comment", "Logged_By", "Txn_ID"]
    worksheet.update('A1:G1', [headers])
    print("Successfully created 'Ledger' tab and added headers!")
