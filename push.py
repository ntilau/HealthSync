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


import csv
import glob

SAMSUNG_HEALTH_DIR = os.path.join(os.path.dirname(__file__), "Samsung_Health")

def upload_all_day_summaries(service, samsung_health_dir=SAMSUNG_HEALTH_DIR):
    """
    Find all day_summary CSVs in the Samsung Health export and upload each day's step count to Google Fit.
    """
    pattern = os.path.join(samsung_health_dir, "*", "com.samsung.shealth.activity.day_summary.*.csv")
    files = glob.glob(pattern)
    print(f"Found {len(files)} day_summary CSVs.")
    for file in files:
        with open(file, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Defensive: skip rows with missing or zero step_count or day_time
                try:
                    step_count = int(float(row.get("step_count", 0)))
                    day_time = row.get("day_time")
                    if not day_time or step_count <= 0:
                        continue
                    # Convert day_time (e.g. 2025-04-17 00:00:00.000) to UTC start/end nanos
                    dt = datetime.datetime.strptime(day_time[:19], "%Y-%m-%d %H:%M:%S")
                    start = int(dt.replace(tzinfo=datetime.timezone.utc).timestamp() * 1e9)
                    end = int((dt + datetime.timedelta(days=1)).replace(tzinfo=datetime.timezone.utc).timestamp() * 1e9) - 1
                    data_set = {
                        "dataSourceId": "derived:com.google.step_count.delta:com.google.android.gms:estimated_steps",
                        "minStartTimeNs": start,
                        "maxEndTimeNs": end,
                        "point": [{
                            "startTimeNanos": start,
                            "endTimeNanos": end,
                            "dataTypeName": "com.google.step_count.delta",
                            "value": [{"intVal": step_count}]
                        }]
                    }
                    dataset_id = f"{start}-{end}"
                    service.users().dataSources().datasets().patch(
                        userId='me',
                        dataSourceId=data_set['dataSourceId'],
                        datasetId=dataset_id,
                        body=data_set
                    ).execute()
                    print(f"Uploaded {step_count} steps for {day_time} from {os.path.basename(file)}")
                except Exception as e:
                    print(f"Error processing row: {row} in {file}: {e}")

if __name__ == "__main__":
    service = get_fit_service()
    upload_all_day_summaries(service)
