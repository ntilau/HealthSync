import os
import sys
import datetime
import json
import pickle
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import csv
import glob

SCOPES = [
    'https://www.googleapis.com/auth/fitness.activity.write',
    'https://www.googleapis.com/auth/fitness.location.write',
    'https://www.googleapis.com/auth/fitness.body.write',
    'https://www.googleapis.com/auth/fitness.nutrition.write',
    'https://www.googleapis.com/auth/fitness.sleep.write',
]

TOKEN_PATH = os.path.join(os.path.dirname(__file__), 'token.pickle')
UPLOAD_LOG_PATH = os.path.join(os.path.dirname(__file__), 'uploaded_dates.json')
BASE_DIR = os.path.dirname(__file__)
SAMSUNG_HEALTH_DIR = os.path.join(BASE_DIR, "Samsung_Health")

# Data source IDs — all share the OAuth client prefix from credentials.json
CLIENT_PREFIX = "362088348000"
STREAM = "samsung_health_import"
DS = {
    "steps":    f"raw:com.google.step_count.delta:{CLIENT_PREFIX}:{STREAM}",
    "distance": f"raw:com.google.distance.delta:{CLIENT_PREFIX}:{STREAM}",
    "calories": f"raw:com.google.calories.expended:{CLIENT_PREFIX}:{STREAM}",
    "weight":   f"raw:com.google.weight:{CLIENT_PREFIX}:{STREAM}",
    "height":   f"raw:com.google.height:{CLIENT_PREFIX}:{STREAM}",
    "body_fat": f"raw:com.google.body.fat.percentage:{CLIENT_PREFIX}:{STREAM}",
    "hydration": f"raw:com.google.hydration:{CLIENT_PREFIX}:{STREAM}",
    "heart_points": f"raw:com.google.heart_minutes:{CLIENT_PREFIX}:{STREAM}",
    "sleep":    f"raw:com.google.sleep.segment:{CLIENT_PREFIX}:{STREAM}",
}

# Heart Points: 1 pt per minute of moderate activity, 2 pts per minute of vigorous
MODERATE_PACE_KMH = 4.0   # brisk walking threshold
VIGOROUS_PACE_KMH = 7.0   # running threshold


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


# ---- upload log ----

def load_upload_log():
    if os.path.exists(UPLOAD_LOG_PATH):
        with open(UPLOAD_LOG_PATH) as f:
            data = json.load(f)
    else:
        return {}

    if isinstance(data, list):
        return {"steps": set(data), "distance": set(), "calories": set()}

    return {metric: set(dates) for metric, dates in data.items()}


def save_upload_log(upload_log):
    with open(UPLOAD_LOG_PATH, 'w') as f:
        json.dump({m: sorted(ds) for m, ds in upload_log.items()}, f)


# ---- helpers ----

def parse_day_time(value):
    if not value:
        return None
    value = value.strip().rstrip('.')
    try:
        ms = int(value)
        return datetime.datetime.fromtimestamp(ms / 1000, tz=datetime.timezone.utc)
    except ValueError:
        pass
    try:
        return datetime.datetime.strptime(value[:19], "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=datetime.timezone.utc
        )
    except ValueError:
        return None


def push_point(service, data_source_id, start_ns, end_ns, data_type_name, value):
    data_set = {
        "dataSourceId": data_source_id,
        "minStartTimeNs": start_ns,
        "maxEndTimeNs": end_ns,
        "point": [{
            "startTimeNanos": start_ns,
            "endTimeNanos": end_ns,
            "dataTypeName": data_type_name,
            "value": [value]
        }]
    }
    service.users().dataSources().datasets().patch(
        userId='me',
        dataSourceId=data_source_id,
        datasetId=f"{start_ns}-{end_ns}",
        body=data_set
    ).execute()


def logged(metric, date_key, upload_log, seen):
    upload_log.setdefault(metric, set())
    seen.setdefault(metric, set())
    return date_key in upload_log[metric] or date_key in seen[metric]


def mark_done(metric, date_key, upload_log, seen):
    upload_log[metric].add(date_key)
    seen[metric].add(date_key)


# ---- CSV parsers for daily summary metrics ----

def push_daily_metrics(service, upload_log, seen):
    """Push steps, distance, calories from daily-summary CSVs."""
    patterns = [
        "com.samsung.shealth.tracker.pedometer_day_summary.*.csv",
        "com.samsung.shealth.activity.day_summary.*.csv",
    ]
    files = []
    for pat in patterns:
        files.extend(glob.glob(os.path.join(SAMSUNG_HEALTH_DIR, "*", pat)))

    print(f"\n--- Daily metrics: {len(files)} CSV(s) ---")
    for file in files:
        with open(file, newline="", encoding='utf-8-sig') as f:
            next(f)
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    sc = int(float(row.get("step_count", 0)))
                    dist = float(row.get("distance", 0)) if row.get("distance") else 0.0
                    cal = float(row.get("calorie", 0)) if row.get("calorie") else 0.0
                    day_time_raw = row.get("day_time")
                    if sc <= 0 and dist <= 0.0 and cal <= 0.0:
                        continue
                    dt = parse_day_time(day_time_raw)
                    if not dt:
                        continue

                    dk = str(dt.date())
                    start_ns = int(dt.timestamp() * 1e9)
                    end_ns = int((dt + datetime.timedelta(days=1)).timestamp() * 1e9) - 1

                    if sc > 0 and not logged("steps", dk, upload_log, seen):
                        push_point(service, DS["steps"], start_ns, end_ns,
                                   "com.google.step_count.delta", {"intVal": sc})
                        mark_done("steps", dk, upload_log, seen)
                        save_upload_log(upload_log)
                        print(f"  Steps:     {sc:>6}          {dk}")

                    if dist > 0 and not logged("distance", dk, upload_log, seen):
                        push_point(service, DS["distance"], start_ns, end_ns,
                                   "com.google.distance.delta", {"fpVal": dist})
                        mark_done("distance", dk, upload_log, seen)
                        save_upload_log(upload_log)
                        print(f"  Distance:  {dist:>8.1f} m     {dk}")

                    if cal > 0 and not logged("calories", dk, upload_log, seen):
                        push_point(service, DS["calories"], start_ns, end_ns,
                                   "com.google.calories.expended", {"fpVal": cal})
                        mark_done("calories", dk, upload_log, seen)
                        save_upload_log(upload_log)
                        print(f"  Calories:  {cal:>8.1f} kcal  {dk}")
                except HttpError as e:
                    print(f"  API error: {e}")
                except Exception as e:
                    print(f"  Error: {e}")


# ---- body metrics: weight, height, body fat ----

def push_body_metrics(service, upload_log, seen):
    print("\n--- Body metrics ---")

    # Weight (includes body fat % in some rows)
    for file in glob.glob(os.path.join(SAMSUNG_HEALTH_DIR, "*", "com.samsung.health.weight.*.csv")):
        with open(file, newline="", encoding='utf-8-sig') as f:
            next(f)
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    start_time = row.get("start_time", "")
                    dt = parse_day_time(start_time)
                    if not dt:
                        continue
                    dk = str(dt.date())

                    weight = float(row.get("weight", 0)) if row.get("weight") else 0.0
                    body_fat = float(row.get("body_fat", 0)) if row.get("body_fat") else 0.0

                    if weight > 0 and not logged("weight", dk, upload_log, seen):
                        push_point(service, DS["weight"], int(dt.timestamp() * 1e9),
                                   int(dt.timestamp() * 1e9),
                                   "com.google.weight", {"fpVal": weight})
                        mark_done("weight", dk, upload_log, seen)
                        save_upload_log(upload_log)
                        print(f"  Weight:    {weight:.1f} kg       {dk}")

                    if body_fat > 0 and not logged("body_fat", dk, upload_log, seen):
                        push_point(service, DS["body_fat"], int(dt.timestamp() * 1e9),
                                   int(dt.timestamp() * 1e9),
                                   "com.google.body.fat.percentage", {"fpVal": body_fat})
                        mark_done("body_fat", dk, upload_log, seen)
                        save_upload_log(upload_log)
                        print(f"  Body fat:  {body_fat:.1f} %        {dk}")
                except HttpError as e:
                    print(f"  API error: {e}")
                except Exception as e:
                    print(f"  Error: {e}")

    # Height
    for file in glob.glob(os.path.join(SAMSUNG_HEALTH_DIR, "*", "com.samsung.health.height.*.csv")):
        with open(file, newline="", encoding='utf-8-sig') as f:
            next(f)
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    start_time = row.get("start_time", "")
                    dt = parse_day_time(start_time)
                    if not dt:
                        continue
                    dk = str(dt.date())
                    height = float(row.get("height", 0)) if row.get("height") else 0.0

                    if height > 0 and not logged("height", dk, upload_log, seen):
                        push_point(service, DS["height"], int(dt.timestamp() * 1e9),
                                   int(dt.timestamp() * 1e9),
                                   "com.google.height", {"fpVal": height / 100.0})
                        mark_done("height", dk, upload_log, seen)
                        save_upload_log(upload_log)
                        print(f"  Height:    {height:.0f} cm        {dk}")
                except HttpError as e:
                    print(f"  API error: {e}")
                except Exception as e:
                    print(f"  Error: {e}")


# ---- hydration ----

def push_hydration(service, upload_log, seen):
    print("\n--- Hydration ---")
    for file in glob.glob(os.path.join(SAMSUNG_HEALTH_DIR, "*", "com.samsung.health.water_intake.*.csv")):
        with open(file, newline="", encoding='utf-8-sig') as f:
            next(f)
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    start_time = row.get("start_time", "")
                    dt = parse_day_time(start_time)
                    if not dt:
                        continue
                    dk = str(dt.date())
                    amount = float(row.get("amount", 0)) if row.get("amount") else 0.0

                    if amount > 0 and not logged("hydration", dk, upload_log, seen):
                        push_point(service, DS["hydration"], int(dt.timestamp() * 1e9),
                                   int(dt.timestamp() * 1e9),
                                   "com.google.hydration", {"fpVal": amount / 1000.0})
                        mark_done("hydration", dk, upload_log, seen)
                        save_upload_log(upload_log)
                        print(f"  Water:     {amount:.0f} ml        {dk}")
                except HttpError as e:
                    print(f"  API error: {e}")
                except Exception as e:
                    print(f"  Error: {e}")


# ---- sleep ----

def push_sleep(service, upload_log, seen):
    print("\n--- Sleep ---")
    for file in glob.glob(os.path.join(SAMSUNG_HEALTH_DIR, "*", "com.samsung.shealth.sleep.*.csv")):
        with open(file, newline="", encoding='utf-8-sig') as f:
            next(f)
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    start_time = row.get("com.samsung.health.sleep.start_time")
                    end_time = row.get("com.samsung.health.sleep.end_time")
                    if not start_time or not end_time:
                        continue
                    start_dt = parse_day_time(start_time)
                    end_dt = parse_day_time(end_time)
                    if not start_dt or not end_dt:
                        continue
                    dk = str(start_dt.date())

                    if logged("sleep", dk, upload_log, seen):
                        continue

                    push_point(service, DS["sleep"],
                               int(start_dt.timestamp() * 1e9),
                               int(end_dt.timestamp() * 1e9),
                               "com.google.sleep.segment", {"intVal": 2})
                    mark_done("sleep", dk, upload_log, seen)
                    save_upload_log(upload_log)
                    dur = (end_dt - start_dt).total_seconds() / 3600
                    print(f"  Sleep:     {dur:.1f}h          {dk}")
                except HttpError as e:
                    print(f"  API error: {e}")
                except Exception as e:
                    print(f"  Error: {e}")


# ---- heart rate generation ----

def calc_heart_points(speed_kmh, duration_min):
    """Return Heart Points for an activity based on speed and duration."""
    if speed_kmh >= VIGOROUS_PACE_KMH:
        return round(duration_min * 2, 1)
    elif speed_kmh >= MODERATE_PACE_KMH:
        return round(duration_min * 1, 1)
    else:
        return 0.0


def push_heart_points(service, upload_log, seen):
    print("\n--- Heart Points ---")

    daily_points = {}  # {date_key: total_points}

    # From exercise data
    for file in glob.glob(os.path.join(SAMSUNG_HEALTH_DIR, "*", "com.samsung.shealth.exercise.*.csv")):
        with open(file, newline="", encoding='utf-8-sig') as f:
            next(f)
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    start_time = row.get("com.samsung.health.exercise.start_time")
                    duration = int(row.get("com.samsung.health.exercise.duration", 0))
                    distance = float(row.get("com.samsung.health.exercise.distance", 0)) if row.get("com.samsung.health.exercise.distance") else 0.0

                    if not start_time or duration <= 0:
                        continue
                    start_dt = parse_day_time(start_time)
                    if not start_dt:
                        continue

                    dur_s = duration / 1000.0 if duration > 100000 else duration
                    dur_min = dur_s / 60.0
                    speed_kmh = (distance / 1000.0) / (dur_s / 3600.0) if dur_s > 0 else 0
                    points = calc_heart_points(speed_kmh, dur_min)

                    dk = str(start_dt.date())
                    daily_points[dk] = daily_points.get(dk, 0) + points
                except Exception:
                    continue

    # From daily step counts: estimate moderate-active minutes
    for file in glob.glob(os.path.join(SAMSUNG_HEALTH_DIR, "*", "com.samsung.shealth.activity.day_summary.*.csv")):
        with open(file, newline="", encoding='utf-8-sig') as f:
            next(f)
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    day_time_raw = row.get("day_time")
                    dt = parse_day_time(day_time_raw)
                    if not dt:
                        continue
                    dk = str(dt.date())
                    sc = int(float(row.get("step_count", 0)))

                    if sc >= 8000:
                        active_min = 30 + (sc - 8000) / 2000 * 15
                    elif sc >= 5000:
                        active_min = (sc - 5000) / 3000 * 30
                    else:
                        active_min = 0

                    if active_min > 0:
                        daily_points[dk] = daily_points.get(dk, 0) + round(active_min * 1.0, 1)
                except Exception:
                    continue

    count = 0
    for dk, points in sorted(daily_points.items()):
        if logged("heart_points", dk, upload_log, seen):
            continue
        if points <= 0:
            continue

        dt = datetime.datetime.strptime(dk, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc)
        start_ns = int(dt.timestamp() * 1e9)
        end_ns = int((dt + datetime.timedelta(days=1)).timestamp() * 1e9) - 1

        push_point(service, DS["heart_points"], start_ns, end_ns,
                   "com.google.heart_minutes", {"fpVal": points})
        mark_done("heart_points", dk, upload_log, seen)
        save_upload_log(upload_log)
        count += 1
        print(f"  Heart Points: {points:>5.1f}        {dk}")

    print(f"  Uploaded {count} days of Heart Points.")


# ---- orchestration ----

def push_all():
    service = get_fit_service()
    upload_log = load_upload_log()
    seen = {}

    push_daily_metrics(service, upload_log, seen)
    push_body_metrics(service, upload_log, seen)
    push_hydration(service, upload_log, seen)
    push_sleep(service, upload_log, seen)
    push_heart_points(service, upload_log, seen)

    print("\nDone.")


if __name__ == "__main__":
    push_all()
