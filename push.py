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

# ── config ──────────────────────────────────────────────────────────

SCOPES = [
    'https://www.googleapis.com/auth/fitness.activity.write',
    'https://www.googleapis.com/auth/fitness.location.write',
    'https://www.googleapis.com/auth/fitness.body.write',
    'https://www.googleapis.com/auth/fitness.nutrition.write',
    'https://www.googleapis.com/auth/fitness.sleep.write',
]

BASE_DIR = os.path.dirname(__file__)
TOKEN_PATH = os.path.join(BASE_DIR, 'token.pickle')
LOG_PATH = os.path.join(BASE_DIR, 'uploaded_dates.json')
SAMSUNG_DIR = os.path.join(BASE_DIR, "Samsung_Health")

CLIENT_PREFIX = "362088348000"
STREAM = "samsung_health_import"

MODERATE_SPEED = 4.0   # km/h — 1 heart point per minute
VIGOROUS_SPEED = 7.0   # km/h — 2 heart points per minute

# ── metric registry ─────────────────────────────────────────────────
#   key       data-type-name                  value-key  value-type    (numeric types: intVal or fpVal)

METRICS = {
    "steps":        ("com.google.step_count.delta",        "intVal", int),
    "minute_steps": ("com.google.step_count.delta",        "intVal", int),
    "distance":     ("com.google.distance.delta",          "fpVal",  float),
    "calories":     ("com.google.calories.expended",       "fpVal",  float),
    "weight":       ("com.google.weight",                  "fpVal",  float),
    "height":       ("com.google.height",                  "fpVal",  float),
    "body_fat":     ("com.google.body.fat.percentage",     "fpVal",  float),
    "hydration":    ("com.google.hydration",               "fpVal",  float),
    "heart_points": ("com.google.heart_minutes",           "fpVal",  float),
    "sleep":        ("com.google.sleep.segment",           "intVal", int),
}

# derive data-source IDs
DS = {key: f"raw:{dtype}:{CLIENT_PREFIX}:{STREAM}" for key, (dtype, _, _) in METRICS.items()}

# ── auth ────────────────────────────────────────────────────────────

def get_fit_service():
    creds = None
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, 'rb') as f:
            creds = pickle.load(f)

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
                    "has not been added as a test user.\n\n"
                    "  → Go to https://console.cloud.google.com/apis/credentials/consent\n"
                    "    and add your Google account under 'Test users'.\n"
                )
        with open(TOKEN_PATH, 'wb') as f:
            pickle.dump(creds, f)

    return build('fitness', 'v1', credentials=creds)

# ── upload log ──────────────────────────────────────────────────────

def load_log():
    if not os.path.exists(LOG_PATH):
        return {}
    with open(LOG_PATH) as f:
        data = json.load(f)
    if isinstance(data, list):
        return {"steps": set(data)}
    return {m: set(d) for m, d in data.items()}


def save_log(log):
    with open(LOG_PATH, 'w') as f:
        json.dump({m: sorted(d) for m, d in log.items()}, f)

# ── helpers ─────────────────────────────────────────────────────────

def parse_time(value):
    """Parse Samsung Health timestamps: epoch-ms or 'YYYY-MM-DD HH:MM:SS.fff'."""
    if not value:
        return None
    value = value.strip().rstrip('.')
    try:
        return datetime.datetime.fromtimestamp(int(value) / 1000, tz=datetime.timezone.utc)
    except ValueError:
        pass
    try:
        return datetime.datetime.strptime(value[:19], "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=datetime.timezone.utc)
    except ValueError:
        return None


def date_key(dt):
    return str(dt.date())


def nano(dt):
    return int(dt.timestamp() * 1e9)


def push_point(service, metric, start_ns, end_ns, value):
    dtype, val_key, _ = METRICS[metric]
    body = {
        "dataSourceId": DS[metric],
        "minStartTimeNs": start_ns,
        "maxEndTimeNs": end_ns,
        "point": [{
            "startTimeNanos": start_ns,
            "endTimeNanos": end_ns,
            "dataTypeName": dtype,
            "value": [{val_key: value}]
        }]
    }
    service.users().dataSources().datasets().patch(
        userId='me',
        dataSourceId=DS[metric],
        datasetId=f"{start_ns}-{end_ns}",
        body=body
    ).execute()


def skip(metric, dk, log, seen):
    log.setdefault(metric, set())
    seen.setdefault(metric, set())
    return dk in log[metric] or dk in seen[metric]


def mark(metric, dk, log, seen):
    log[metric].add(dk)
    seen[metric].add(dk)


def day_range(dt):
    """Return (start_ns, end_ns) covering the full UTC day of dt."""
    start = int(dt.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1e9)
    end = start + 86400_000_000_000 - 1
    return start, end


def csv_files(*name_fragments):
    """Return all CSVs matching every fragment somewhere in their filename."""
    files = []
    for frag in name_fragments:
        files.extend(glob.glob(os.path.join(SAMSUNG_DIR, "*", f"*{frag}*.csv")))
    return files


def iter_csv(file, field_map):
    """Yield {local_name: value} dicts for each row.  Skips Samsung's metadata row.
       field_map: {csv_column: local_name}  — only listed columns are extracted."""
    with open(file, newline="", encoding='utf-8-sig') as f:
        next(f)  # Samsung metadata row
        reader = csv.DictReader(f)
        for row in reader:
            yield {local: row.get(col) for col, local in field_map.items()}

# ── section header ──────────────────────────────────────────────────

def section(title):
    print(f"\n{'─' * 60}\n  {title}\n{'─' * 60}")

# ── daily metrics (steps, distance, calories) ───────────────────────

def push_daily_metrics(service, log, seen):
    section("Daily Metrics — steps, distance, calories")

    for file in csv_files("pedometer_day_summary", "activity.day_summary"):
        for r in iter_csv(file, {"step_count": "steps", "distance": "dist",
                                  "calorie": "cal", "day_time": "day_time"}):
            try:
                sc = int(float(r["steps"] or 0))
                dist = float(r["dist"] or 0)
                cal = float(r["cal"] or 0)
                dt = parse_time(r["day_time"])
                if not dt or (sc == 0 and dist == 0 and cal == 0):
                    continue

                dk, s, e = date_key(dt), *day_range(dt)

                for metric, val, fmt in [
                    ("steps", sc, "{:>6}"),
                    ("distance", dist, "{:>8.1f} m"),
                    ("calories", cal, "{:>8.1f} kcal"),
                ]:
                    if val > 0 and not skip(metric, dk, log, seen):
                        push_point(service, metric, s, e, val)
                        mark(metric, dk, log, seen)
                        save_log(log)
                        print(f"  {metric:<12} {fmt.format(val):>16}  {dk}")
            except HttpError as e:
                print(f"  API error: {e}")

# ── body metrics (weight, height, body fat) ─────────────────────────

def push_body_metrics(service, log, seen):
    section("Body Metrics — weight, height, body fat")

    for file in csv_files("com.samsung.health.weight"):
        for r in iter_csv(file, {"start_time": "t", "weight": "w", "body_fat": "bf"}):
            try:
                dt = parse_time(r["t"])
                if not dt:
                    continue
                dk, ns = date_key(dt), nano(dt)

                for metric, raw, label, conv in [
                    ("weight", r["w"], "kg", lambda v: v),
                    ("body_fat", r["bf"], "%", lambda v: v),
                ]:
                    val = float(raw or 0)
                    if val > 0 and not skip(metric, dk, log, seen):
                        push_point(service, metric, ns, ns, conv(val))
                        mark(metric, dk, log, seen)
                        save_log(log)
                        print(f"  {metric:<12} {val:>8.1f} {label}    {dk}")
            except HttpError as e:
                print(f"  API error: {e}")

    for file in csv_files("com.samsung.health.height"):
        for r in iter_csv(file, {"start_time": "t", "height": "h"}):
            try:
                dt = parse_time(r["t"])
                if not dt:
                    continue
                dk, ns = date_key(dt), nano(dt)
                h = float(r["h"] or 0)
                if h > 0 and not skip("height", dk, log, seen):
                    push_point(service, "height", ns, ns, h / 100.0)
                    mark("height", dk, log, seen)
                    save_log(log)
                    print(f"  height       {h:>8.0f} cm      {dk}")
            except HttpError as e:
                print(f"  API error: {e}")

# ── hydration ───────────────────────────────────────────────────────

def push_hydration(service, log, seen):
    section("Hydration — water intake")

    for file in csv_files("water_intake"):
        for r in iter_csv(file, {"start_time": "t", "amount": "ml"}):
            try:
                dt = parse_time(r["t"])
                if not dt:
                    continue
                dk, ns = date_key(dt), nano(dt)
                ml = float(r["ml"] or 0)
                if ml > 0 and not skip("hydration", dk, log, seen):
                    push_point(service, "hydration", ns, ns, ml / 1000.0)
                    mark("hydration", dk, log, seen)
                    save_log(log)
                    print(f"  hydration     {ml:>8.0f} ml      {dk}")
            except HttpError as e:
                print(f"  API error: {e}")

# ── sleep ───────────────────────────────────────────────────────────

def push_sleep(service, log, seen):
    section("Sleep — sleep segments")

    for file in csv_files("com.samsung.shealth.sleep"):
        for r in iter_csv(file, {
            "com.samsung.health.sleep.start_time": "start",
            "com.samsung.health.sleep.end_time": "end",
        }):
            try:
                s_dt = parse_time(r["start"])
                e_dt = parse_time(r["end"])
                if not s_dt or not e_dt:
                    continue
                dk = date_key(s_dt)
                if skip("sleep", dk, log, seen):
                    continue

                push_point(service, "sleep", nano(s_dt), nano(e_dt), 2)  # 2 = generic sleep
                mark("sleep", dk, log, seen)
                save_log(log)
                dur_h = (e_dt - s_dt).total_seconds() / 3600
                print(f"  sleep         {dur_h:>8.1f} h       {dk}")
            except HttpError as e:
                print(f"  API error: {e}")

# ── minute-level steps + heart points ────────────────────────────────

def push_minute_steps_and_heart_points(service, log, seen):
    """Push minute-resolution step data AND compute Heart Points in one pass.
       Each pedometer_step_count row is a ~1-minute interval with its own
       start/end time, step count, speed, distance, and calorie data."""

    section("Minute-Level Steps & Heart Points — pedometer_step_count")

    daily_points = {}    # {date_key: heart_points}
    daily_intervals = {} # {date_key: [point_dict]}

    for file in csv_files("pedometer_step_count"):
        for r in iter_csv(file, {
            "com.samsung.health.step_count.start_time": "t",
            "com.samsung.health.step_count.end_time":   "et",
            "com.samsung.health.step_count.count":       "steps",
            "com.samsung.health.step_count.speed":       "speed",
            "com.samsung.health.step_count.distance":    "dist",
            "com.samsung.health.step_count.calorie":     "cal",
        }):
            try:
                s_dt = parse_time(r["t"])
                e_dt = parse_time(r["et"])
                if not s_dt or not e_dt:
                    continue

                count = int(float(r["steps"] or 0))
                speed = float(r["speed"] or 0)
                dist  = float(r["dist"] or 0)
                cal   = float(r["cal"] or 0)

                dk = date_key(s_dt)
                daily_intervals.setdefault(dk, []).append({
                    "start_ns": nano(s_dt),
                    "end_ns":   nano(e_dt),
                    "steps":    count,
                    "distance": dist,
                    "calories": cal,
                })

                # Heart Points from speed
                if speed >= VIGOROUS_SPEED:
                    daily_points[dk] = daily_points.get(dk, 0) + 2.0
                elif speed >= MODERATE_SPEED:
                    daily_points[dk] = daily_points.get(dk, 0) + 1.0
            except Exception:
                continue

    # ---- push minute-level steps, distance, calories per day ----

    step_uploaded = 0
    dist_uploaded = 0
    cal_uploaded  = 0
    for dk, intervals in sorted(daily_intervals.items()):
        if skip("minute_steps", dk, log, seen):
            continue

        dt = datetime.datetime.strptime(dk, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc)
        day_start, day_end = day_range(dt)

        # Build multi-point datasets for this day
        for metric, val_field, dtype_key in [
            ("steps",    "steps",    "com.google.step_count.delta"),
            ("distance", "distance", "com.google.distance.delta"),
            ("calories", "calories", "com.google.calories.expended"),
        ]:
            points = []
            for iv in intervals:
                v = iv[val_field]
                if v <= 0:
                    continue
                val_key, _ = METRICS[metric][1], METRICS[metric][2]
                points.append({
                    "startTimeNanos": iv["start_ns"],
                    "endTimeNanos":   iv["end_ns"],
                    "dataTypeName":   dtype_key,
                    "value":          [{val_key: val_key == "intVal" and int(v) or v}],
                })

            if not points:
                continue

            body = {
                "dataSourceId": DS[metric],
                "minStartTimeNs": day_start,
                "maxEndTimeNs": day_end,
                "point": points,
            }
            service.users().dataSources().datasets().patch(
                userId='me',
                dataSourceId=DS[metric],
                datasetId=f"{day_start}-{day_end}",
                body=body,
            ).execute()

            if metric == "steps":
                step_uploaded += len(points)
            elif metric == "distance":
                dist_uploaded += len(points)
            else:
                cal_uploaded += len(points)

        mark("minute_steps", dk, log, seen)
        save_log(log)

        total_steps = sum(iv["steps"] for iv in intervals)
        total_dist  = sum(iv["distance"] for iv in intervals)
        print(f"  minute_steps  {total_steps:>6} steps  {len(intervals):>4} pts  "
              f"{total_dist:>8.1f} m     {dk}")

    print(f"  → {step_uploaded} step + {dist_uploaded} distance + {cal_uploaded} calorie points")
    print(f"     across {len([dk for dk in daily_intervals if not skip('minute_steps', dk, log, seen)])} new days")

    # ---- push Heart Points ----

    hp_uploaded = 0
    for dk in sorted(daily_points):
        pts = daily_points[dk]
        if pts <= 0 or skip("heart_points", dk, log, seen):
            continue
        dt = datetime.datetime.strptime(dk, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc)
        push_point(service, "heart_points", *day_range(dt), round(pts, 1))
        mark("heart_points", dk, log, seen)
        save_log(log)
        hp_uploaded += 1
        print(f"  heart_points  {pts:>8.1f} pts    {dk}")

    print(f"  → {hp_uploaded} new heart-point days")

    # Fallback: exercise sessions not covered by minute-level data
    section("Heart Points — exercise fallback")
    ex_daily = {}
    for file in csv_files("com.samsung.shealth.exercise"):
        for r in iter_csv(file, {
            "com.samsung.health.exercise.start_time": "t",
            "com.samsung.health.exercise.duration": "dur",
            "com.samsung.health.exercise.distance": "dist",
        }):
            try:
                dt = parse_time(r["t"])
                dur_ms = int(r["dur"] or 0)
                dist_m = float(r["dist"] or 0)
                if not dt or dur_ms <= 0:
                    continue
                dur_min = (dur_ms / 1000 if dur_ms > 100_000 else dur_ms) / 60
                speed = (dist_m / 1000) / (dur_min / 60) if dur_min > 0 else 0
                if speed >= VIGOROUS_SPEED:
                    pts = round(dur_min * 2, 1)
                elif speed >= MODERATE_SPEED:
                    pts = round(dur_min * 1, 1)
                else:
                    pts = 0
                dk = date_key(dt)
                if pts > 0 and dk not in daily_points and not skip("heart_points", dk, log, seen):
                    ex_daily[dk] = ex_daily.get(dk, 0) + pts
            except Exception:
                continue

    ex_up = 0
    for dk in sorted(ex_daily):
        pts = ex_daily[dk]
        if pts <= 0:
            continue
        dt = datetime.datetime.strptime(dk, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc)
        push_point(service, "heart_points", *day_range(dt), round(pts, 1))
        mark("heart_points", dk, log, seen)
        save_log(log)
        ex_up += 1
        print(f"  heart_points  {pts:>8.1f} pts    {dk}  (exercise)")

    if ex_up:
        print(f"  → {ex_up} exercise-fallback days")

# ── main ────────────────────────────────────────────────────────────

def push_all():
    service = get_fit_service()
    log = load_log()
    seen = {}

    counts_before = {m: len(log.get(m, set())) for m in METRICS}

    push_daily_metrics(service, log, seen)
    push_body_metrics(service, log, seen)
    push_hydration(service, log, seen)
    push_sleep(service, log, seen)
    push_minute_steps_and_heart_points(service, log, seen)

    section("Summary")
    for m in METRICS:
        before = counts_before.get(m, 0)
        after = len(log.get(m, set()))
        new = after - before
        print(f"  {m:<14} {before:>5} → {after:<5}  (+{new})" if new else
              f"  {m:<14} {after:>5}  (no change)")

    print(f"\n{'─' * 60}\nDone.\n")


if __name__ == "__main__":
    push_all()
