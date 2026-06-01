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
    'https://www.googleapis.com/auth/fitness.body.read',
    'https://www.googleapis.com/auth/fitness.nutrition.read',
    'https://www.googleapis.com/auth/fitness.sleep.read',
]

TOKEN_PATH = os.path.join(os.path.dirname(__file__), 'token_read.pickle')
BASE_DIR = os.path.dirname(__file__)


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
                creds_path = os.path.join(BASE_DIR, 'credentials.json')
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
                        if "step_count" in ds_id:
                            entry["steps"] += val["intVal"]
                    elif "fpVal" in val:
                        if "distance" in ds_id:
                            entry["distance_m"] += val["fpVal"]
                        elif "calories" in ds_id:
                            entry["calories"] += val["fpVal"]

    return results


def fetch_body_metrics(service, start_date, end_date):
    """Fetch latest weight, height, body fat in range."""
    results = {}
    for dtype, key, field in [
        ("com.google.weight", "weight_kg", "fpVal"),
        ("com.google.height", "height_m", "fpVal"),
        ("com.google.body.fat.percentage", "body_fat_pct", "fpVal"),
    ]:
        try:
            resp = service.users().dataSources().datasets().get(
                userId="me",
                dataSourceId=f"derived:{dtype}:com.google.android.gms:merge_{dtype.split('.')[-1]}",
                datasetId=f"{int(start_date.strftime('%s'))}000000000-{int(end_date.strftime('%s'))}000000000",
            ).execute()
            for point in resp.get("point", []):
                for val in point.get("value", []):
                    if field in val:
                        results[key] = val[field]
        except Exception:
            pass
    return results


def fetch_sleep(service, start_date, end_date):
    """Return list of sleep sessions in range."""
    sessions = []
    try:
        start_ns = int(datetime.datetime.combine(start_date, datetime.time.min, tzinfo=datetime.timezone.utc).timestamp() * 1e9)
        end_ns = int(datetime.datetime.combine(end_date, datetime.time.max, tzinfo=datetime.timezone.utc).timestamp() * 1e9)
        resp = service.users().sessions().list(
            userId="me",
            startTime=start_ns,
            endTime=end_ns,
            activityType=72,  # sleep
        ).execute()
        for sess in resp.get("session", []):
            start_ms = int(sess["startTimeMillis"])
            end_ms = int(sess["endTimeMillis"])
            dur = (end_ms - start_ms) / 3600000.0
            sessions.append({
                "date": datetime.datetime.fromtimestamp(start_ms / 1000, tz=datetime.timezone.utc).strftime("%Y-%m-%d"),
                "duration_h": dur,
            })
    except Exception:
        pass
    return sessions


def fetch_heart_points(service, start_date, end_date):
    """Return daily Heart Points for range."""
    start_dt = datetime.datetime.combine(start_date, datetime.time.min, tzinfo=datetime.timezone.utc)
    end_dt = datetime.datetime.combine(end_date, datetime.time.max, tzinfo=datetime.timezone.utc)

    body = {
        "aggregateBy": [{"dataTypeName": "com.google.heart_minutes"}],
        "bucketByTime": {"durationMillis": 86400000},
        "startTimeMillis": int(start_dt.timestamp() * 1000),
        "endTimeMillis": int(end_dt.timestamp() * 1000),
    }

    results = {}
    try:
        response = service.users().dataset().aggregate(userId="me", body=body).execute()
        for bucket in response.get("bucket", []):
            start_ms = int(bucket["startTimeMillis"])
            date_str = datetime.datetime.fromtimestamp(start_ms / 1000, tz=datetime.timezone.utc).strftime("%Y-%m-%d")
            points = 0.0
            for ds in bucket.get("dataset", []):
                for point in ds.get("point", []):
                    for val in point.get("value", []):
                        if "fpVal" in val:
                            points += val["fpVal"]
            if points > 0:
                results[date_str] = points
    except Exception:
        pass
    return results


def print_report(daily, body, sleep_data, hp_data):
    print(f"{'Date':>12}  {'Steps':>10}  {'Dist(km)':>9}  {'Cal(kcal)':>10}  {'HeartPts':>9}  {'Sleep':>6}")
    print("-" * 72)

    total_steps = 0
    total_dist = 0.0
    total_cal = 0.0
    total_sleep = 0.0
    sleep_count = 0

    for date_str in sorted(daily):
        entry = daily[date_str]
        steps = entry["steps"]
        dist_km = entry["distance_m"] / 1000.0
        cal = entry["calories"]
        total_steps += steps
        total_dist += dist_km
        total_cal += cal

        hp = hp_data.get(date_str, 0)
        hp_str = f"{hp:>8.1f}" if hp > 0 else "       -"

        sleep_str = ""
        for s in sleep_data:
            if s.get("date") == date_str:
                sleep_str = f"{s['duration_h']:.1f}h"

        steps_s = f"{steps:>10,}" if steps else "         -"
        dist_s = f"{dist_km:>8.2f}" if dist_km > 0 else "       -"
        cal_s = f"{cal:>9.0f}" if cal > 0 else "        -"
        sleep_s = f"{sleep_str:>6}" if sleep_str else "     -"

        print(f"{date_str:>12}  {steps_s}  {dist_s}  {cal_s}  {hp_str}  {sleep_s}")

    print("-" * 72)
    print(f"{'TOTAL':>12}  {total_steps:>10,}  {total_dist:>8.2f}  {total_cal:>9.0f}")

    if sleep_data:
        total_sleep = sum(s["duration_h"] for s in sleep_data)
        sleep_count = len(sleep_data)
        print(f"\nSleep: {sleep_count} sessions, {total_sleep:.1f}h total")
    if body:
        print(f"Body:  ", end="")
        if "weight_kg" in body:
            print(f"{body['weight_kg']:.1f} kg  ", end="")
        if "height_m" in body:
            print(f"{body['height_m']*100:.0f} cm  ", end="")
        if "body_fat_pct" in body:
            print(f"{body['body_fat_pct']:.1f}% body fat", end="")
        print()


if __name__ == "__main__":
    service = get_fit_service()

    end = datetime.date.today()
    start = end - datetime.timedelta(days=30)

    if len(sys.argv) == 2:
        start = datetime.date.fromisoformat(sys.argv[1])
    elif len(sys.argv) >= 3:
        start = datetime.date.fromisoformat(sys.argv[1])
        end = datetime.date.fromisoformat(sys.argv[2])

    print(f"Fetching health data from {start} to {end}...\n")
    try:
        daily = fetch_daily_metrics(service, start, end)
        body = fetch_body_metrics(service, start, end)
        sleep_data = fetch_sleep(service, start, end)
        hp_data = fetch_heart_points(service, start, end)
        print_report(daily, body, sleep_data, hp_data)
    except HttpError as e:
        if e.resp.status == 403:
            sys.exit(
                f"\nAPI returned 403: {e}\n\n"
                "The Fitness API may not be enabled, or your account lacks access.\n"
                "  1. https://console.cloud.google.com/apis/library/fitness.googleapis.com\n"
                "  2. Ensure your account is a test user on the OAuth consent screen\n"
            )
        print(f"API error: {e}")
