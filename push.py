import os
import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Permissions for reading/writing activity data
SCOPES = ['https://googleapis.com']

def get_fit_service():
    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
    creds = flow.run_local_server(port=0)
    return build('fitness', 'v1', credentials=creds)

def upload_steps(service, step_count):
    now = datetime.datetime.utcnow()
    nanos = int(now.timestamp() * 1e9)
    
    # Define the data point
    data_set = {
        "dataSourceId": "derived:com.google.step_count.delta:com.google.android.gms:estimated_steps",
        "minStartTimeNs": nanos - 3600000000000, # 1 hour ago
        "maxEndTimeNs": nanos,
        "point": [{
            "startTimeNanos": nanos - 3600000000000,
            "endTimeNanos": nanos,
            "dataTypeName": "com.google.step_count.delta",
            "value": [{"intVal": step_count}]
        }]
    }
    
    # Upload to the user's "me" resource
    dataset_id = f"{nanos - 3600000000000}-{nanos}"
    service.users().dataSources().datasets().patch(
        userId='me',
        dataSourceId=data_set['dataSourceId'],
        datasetId=dataset_id,
        body=data_set
    ).execute()
    print(f"Successfully uploaded {step_count} steps.")

# Usage
# service = get_fit_service()
# upload_steps(service, 5000)
