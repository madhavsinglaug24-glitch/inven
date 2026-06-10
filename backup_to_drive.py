import os
import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Configuration
SCOPES = ['https://www.googleapis.com/auth/drive']
SERVICE_ACCOUNT_FILE = 'credentials.json'
DB_FILE = 'inventory.db'
FOLDER_NAME = 'SDE_Backup'

def get_drive_service():
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        print(f"Error: {SERVICE_ACCOUNT_FILE} not found. Please place it in the same directory.")
        return None

    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build('drive', 'v3', credentials=creds)

def find_folder(service, folder_name):
    query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    items = results.get('files', [])
    
    if not items:
        return None
    return items[0]['id']

def upload_backup():
    service = get_drive_service()
    if not service:
        return

    if not os.path.exists(DB_FILE):
        print(f"Error: Database file {DB_FILE} not found.")
        return

    # Find the backup folder ID
    folder_id = find_folder(service, FOLDER_NAME)
    
    if not folder_id:
        print(f"Warning: Folder '{FOLDER_NAME}' not found in Google Drive. Uploading to root directory instead.")
        parents = []
    else:
        parents = [folder_id]

    # Create a timestamped filename
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_filename = f"inventory_backup_{timestamp}.db"

    file_metadata = {
        'name': backup_filename,
        'parents': parents
    }
    
    media = MediaFileUpload(DB_FILE, mimetype='application/x-sqlite3', resumable=True)
    
    print(f"Uploading {backup_filename} to Google Drive...")
    
    try:
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        print(f"Backup successful! File ID: {file.get('id')}")
    except Exception as e:
        print(f"An error occurred during upload: {e}")

if __name__ == '__main__':
    upload_backup()
