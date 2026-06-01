import os
import sys
import datetime
import pickle
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = [
    'https://www.googleapis.com/auth/fitness.activity.read',
    'https://www.googleapis.com/auth/fitness.location.read',
]
TOKEN_PATH = os.path.join(os.path.dirname(__file__), 'token_read.pickle')


def get_fit_service():
    creds = None
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                creds = None
        if not creds:
            try:
                creds_path = os.path.join(os.path.dirname(__file__), 'credentials.json')
                flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
                creds = flow.run_local_server(port=0)
            except RefreshError as e:
                sys.exit(
                    f"\nOAuth failed: {e}\n\n"
                    "Your Google Cloud project is likely in testing mode and your account\n"
                    "has not been added as a test user. To fix this:\n\n"
                    "  1. Go to https://console.cloud.google.com/apis/credentials/consent\n"
                    "  2. Select your project\n"
                    "  3. Under 'Test users', click 'Add Users' and add your Google account\n"
                    "  4. Save and re-run this script\n"
                )
        with open(TOKEN_PATH, 'wb') as token:
            pickle.dump(creds, token)

    return build('fitness', 'v1', credentials=creds)


def fetch_daily_metrics(service, start_date, end_date):
    """Return {date_str: {steps: int, distance_m: float, calories: float}}."""
    start_dt = datetime.datetime.combine(start_date, datetime.time.min, tzinfo=datetime.timezone.utc)
    end_dt = datetime.datetime.combine(end_date, datetime.time.max, tzinfo=datetime.timezone.utc)

    body = {
        "aggregateBy": [
            {"dataTypeName": "com.google.step_count.delta"},
            {"dataTypeName": "com.google.distance.delta"},
            {"dataTypeName": "com.google.calories.expended"},
        ],
        "bucketByTime": {"durationMillis": 86400000},
        "startTimeMillis": int(start_dt.timestamp() * 1000),
        "endTimeMillis": int(end_dt.timestamp() * 1000),
    }

    results = {}
    response = service.users().dataset().aggregate(userId="me", body=body).execute()

    for bucket in response.get("bucket", []):
        start_ms = int(bucket["startTimeMillis"])
        date_str = datetime.datetime.fromtimestamp(
            start_ms / 1000, tz=datetime.timezone.utc
        ).strftime("%Y-%m-%d")
        entry = results.setdefault(date_str, {"steps": 0, "distance_m": 0.0, "calories": 0.0})
        for ds in bucket.get("dataset", []):
            ds_id = ds.get("dataSourceId", "")
            for point in ds.get("point", []):
                for val in point.get("value", []):
                    if "intVal" in val:
                        entry["steps"] += val["intVal"]
                    elif "fpVal" in val:
                        if "distance" in ds_id:
                            entry["distance_m"] += val["fpVal"]
                        elif "calories" in ds_id:
                            entry["calories"] += val["fpVal"]

    return results


def print_daily_metrics(results):
    if not results:
        print("No data found.")
        return

    total_steps = 0
    total_dist = 0.0
    total_cal = 0.0
    print(f"{'Date':>12}  {'Steps':>10}  {'Dist (km)':>10}  {'Cal (kcal)':>12}")
    print("-" * 50)
    for date_str in sorted(results):
        entry = results[date_str]
        steps = entry["steps"]
        dist_km = entry["distance_m"] / 1000.0
        cal = entry["calories"]
        total_steps += steps
        total_dist += dist_km
        total_cal += cal
        steps_str = f"{steps:>10,}" if steps else "         -"
        dist_str = f"{dist_km:>9.2f}" if dist_km > 0 else "        -"
        cal_str = f"{cal:>11.1f}" if cal > 0 else "          -"
        print(f"{date_str:>12}  {steps_str}   {dist_str}  {cal_str}")
    print("-" * 50)
    print(f"{'TOTAL':>12}  {total_steps:>10,}  {total_dist:>9.2f}  {total_cal:>11.1f}")


if __name__ == "__main__":
    service = get_fit_service()

    end = datetime.date.today()
    start = end - datetime.timedelta(days=30)

    if len(sys.argv) == 2:
        start = datetime.date.fromisoformat(sys.argv[1])
    elif len(sys.argv) >= 3:
        start = datetime.date.fromisoformat(sys.argv[1])
        end = datetime.date.fromisoformat(sys.argv[2])

    print(f"Fetching activity data from {start} to {end}...")
    try:
        results = fetch_daily_metrics(service, start, end)
        print_daily_metrics(results)
    except HttpError as e:
        if e.resp.status == 403:
            sys.exit(
                f"\nAPI returned 403: {e}\n\n"
                "The Fitness API may not be enabled, or your account lacks access.\n"
                "Check:\n"
                "  1. https://console.cloud.google.com/apis/library/fitness.googleapis.com\n"
                "  2. Ensure your account is a test user on the OAuth consent screen\n"
            )
        print(f"API error: {e}")
