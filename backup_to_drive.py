import os
import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Configuration
SCOPES = ['https://www.googleapis.com/auth/drive']
CLIENT_SECRETS_FILE = 'client_secrets.json'
TOKEN_FILE = 'token.json'
DB_FILE = 'inventory.db'
FOLDER_NAME = 'SDE_Backup'

def get_drive_service():
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time.
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CLIENT_SECRETS_FILE):
                print(f"Error: {CLIENT_SECRETS_FILE} not found. Please place it in the same directory.")
                return None
            
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

    return build('drive', 'v3', credentials=creds)

def find_folder(service, folder_name):
    query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    items = results.get('files', [])
    
    if not items:
        return None
    return items[0]['id']

def delete_old_backups(service, folder_id):
    if not folder_id:
        return
        
    try:
        # Calculate the date 7 days ago
        seven_days_ago = (datetime.datetime.utcnow() - datetime.timedelta(days=7)).isoformat() + 'Z'
        
        # Query for backup files older than 7 days in the specific folder
        query = f"'{folder_id}' in parents and createdTime < '{seven_days_ago}' and name contains 'inventory_backup_' and trashed=false"
        
        results = service.files().list(q=query, fields="files(id, name, createdTime)").execute()
        items = results.get('files', [])
        
        if items:
            print(f"Found {len(items)} old backup(s) to delete.")
            
        for item in items:
            print(f"Deleting old backup: {item['name']}")
            service.files().delete(fileId=item['id']).execute()
            
    except Exception as e:
        print(f"An error occurred while deleting old backups: {e}")

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
        
        if folder_id:
            delete_old_backups(service, folder_id)
            
    except Exception as e:
        print(f"An error occurred during upload: {e}")

if __name__ == '__main__':
    upload_backup()
