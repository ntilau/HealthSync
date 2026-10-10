#!/usr/bin/env python3
"""
Prepare Google Takeout data for import into Apple Health.
Exports CSV files for various health metrics with timestamps in ISO 8601 UTC.
"""

import json
import csv
import os
import re
from datetime import datetime, timezone, timedelta
import math

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FIT_ALL_DATA_DIR = os.path.join(BASE_DIR, '..', 'raw_exports', 'google_fit', 'all_data')
FIT_INTERVAL_DIR = os.path.join(BASE_DIR, '..', 'raw_exports', 'google_fit', 'daily_activity_metrics')
GOOGLE_HEALTH_DIR = os.path.join(BASE_DIR, '..', 'raw_exports', 'google_health', 'global_export_data')
OUTPUT_DIR = os.path.join(BASE_DIR, '..', 'apple_health_import')

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Metric configurations: output filename, list of source patterns, and value extraction function
# Each source is a tuple: (source_dir, pattern, source_type, skip_if_contains)
# skip_if_contains: list of substrings; if any appears in filename, skip this file.
METRICS = {
    "step_count": {
        "output_file": "step_count.csv",
        "sources": [
            # Pattern to match step count delta files in Fit/All Data/
            (FIT_ALL_DATA_DIR, r".*step_count.*delta.*\.json$", "fit_all_data_step_delta", ["cumulat", "cumulative"]),
        ],
        "description": "Step count delta (steps per interval)",
        "unit": "count",
    },
    "distance": {
        "output_file": "distance.csv",
        "sources": [
            # Interval CSV files in Fit/Daily activity metrics/ (excluding the daily aggregated file)
            (FIT_INTERVAL_DIR, r"^\d{4}-\d{2}-\d{2}\.csv$", "fit_interval_csv", []),
        ],
        "description": "Distance moved (meters)",
        "unit": "m",
    },
    "active_energy": {
        "output_file": "active_energy.csv",
        "sources": [
            # Interval CSV files for calories
            (FIT_INTERVAL_DIR, r"^\d{4}-\d{2}-\d{2}\.csv$", "fit_interval_csv", []),
        ],
        "description": "Active energy burned (kilocalories)",
        "unit": "kcal",
    },
    "heart_rate": {
        "output_file": "heart_rate.csv",
        "sources": [
            # Heart rate bpm files in Fit/All Data/
            (FIT_ALL_DATA_DIR, r".*heart_rate.*bpm.*\.json$", "fit_all_data_heart_rate", []),
        ],
        "description": "Heart rate (beats per minute)",
        "unit": "count/min",
    },
    "body_mass": {
        "output_file": "body_mass.csv",
        "sources": [
            # Weight files in Fit/All Data/ (exclude body fat percentage)
            (FIT_ALL_DATA_DIR, r".*weight.*\.json$", "fit_all_data_weight", ["fat"]),
            (FIT_ALL_DATA_DIR, r".*body.*fat.*percentage.*\.json$", "fit_all_data_body_fat", []),  # We'll skip this via skip_if_contains
        ],
        "description": "Body mass (kilograms)",
        "unit": "kg",
    },
    "height": {
        "output_file": "height.csv",
        "sources": [
            # Height JSON files in Google Health/
            (GOOGLE_HEALTH_DIR, r"^height-\d{4}-\d{2}-\d{2}\.json$", "google_health_daily", []),
        ],
        "description": "Height (meters)",
        "unit": "m",
    },
    "sleep_analysis": {
        "output_file": "sleep_analysis.csv",
        "sources": [
            # Sleep JSON files in Google Health/
            (GOOGLE_HEALTH_DIR, r"^sleep-\d{4}-\d{2}-\d{2}\.json$", "google_health_daily", []),
        ],
        "description": "Sleep analysis (asleep/awake)",
        "unit": "category",  # We'll output startDate, endDate, value (1 for asleep)
    },
}

def nanoseconds_to_iso8601utc(nanoseconds):
    """Convert nanoseconds since epoch to ISO 8601 string in UTC."""
    # nanoseconds to seconds
    seconds = nanoseconds / 1_000_000_000.0
    dt = datetime.fromtimestamp(seconds, tz=timezone.utc)
    return dt.isoformat()

def parse_csv_interval_filename(filename):
    """Extract date from filename like '2026-09-08.csv'."""
    # Remove .csv
    date_str = filename[:-4]
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None

def parse_time_of_day(time_str):
    """Parse time string like '00:00:00.000+02:00' to a time object and timezone offset.
    Returns (time_object, offset_hours) where offset_hours is the offset from UTC in hours.
    """
    # If there's no offset, assume UTC
    if '+' not in time_str and '-' not in time_str:
        time_part = time_str
        offset_hours = 0.0
    else:
        # Find the last + or - that is not part of the time
        plus_pos = time_str.rfind('+')
        minus_pos = time_str.rfind('-')
        if plus_pos == -1 and minus_pos == -1:
            # No offset
            time_part = time_str
            offset_hours = 0.0
        else:
            # Determine which one is the separator (the one that appears after the time)
            # We'll take the later position.
            pos = max(plus_pos, minus_pos)
            separator = time_str[pos]
            time_part = time_str[:pos]
            offset_part = time_str[pos+1:]  # without the sign
            # Parse offset_part which should be HH:MM
            try:
                hours_str, minutes_str = offset_part.split(':')
                offset_hours = int(hours_str) + int(minutes_str) / 60.0
            except (ValueError, IndexError):
                offset_hours = 0.0
            if separator == '-':
                offset_hours = -offset_hours
    # Parse time_part: HH:MM:SS.sss
    try:
        time_obj = datetime.strptime(time_part, "%H:%M:%S.%f").time()
    except ValueError:
        # Maybe no fractional seconds?
        try:
            time_obj = datetime.strptime(time_part, "%H:%M:%S").time()
        except ValueError:
            # If still fails, return a default time and zero offset
            return datetime.min.time(), 0.0
    return time_obj, offset_hours

def combine_date_and_time(date_obj, time_obj, offset_hours):
    """Combine date and time objects, apply offset, and return UTC datetime."""
    # Create naive datetime from date and time
    naive_dt = datetime.combine(date_obj, time_obj)
    # Apply offset: naive_dt is in local time with the given offset from UTC
    # So UTC = naive_dt - offset
    offset = timedelta(hours=offset_hours)
    utc_dt = naive_dt - offset
    return utc_dt.replace(tzinfo=timezone.utc)

def process_fit_all_data_step_delta(filepath):
    """Process a step count delta JSON file from Fit/All Data/.
    Yields (timestamp_iso8601_utc, value) where value is the step delta.
    """
    with open(filepath, 'r') as f:
        data = json.load(f)
    # Expected structure: { "Data Source": "...", "Data Points": [ { "fitValue": [{"value":{"intVal": ...}}], "startTimeNanos": ..., ... } ] }
    if "Data Points" not in data:
        return
    for point in data["Data Points"]:
        if "fitValue" not in point or not point["fitValue"]:
            continue
        # Extract the integer value from fitValue[0].value.intVal
        try:
            val = point["fitValue"][0]["value"]["intVal"]
        except (KeyError, IndexError, TypeError):
            # Try fpVal in case it's a float? But step count should be integer.
            try:
                val = int(point["fitValue"][0]["value"]["fpVal"])
            except (KeyError, IndexError, TypeError, ValueError):
                continue
        start_time_nanos = point.get("startTimeNanos")
        if start_time_nanos is None:
            continue
        timestamp = nanoseconds_to_iso8601utc(start_time_nanos)
        yield timestamp, val

def process_fit_all_data_heart_rate(filepath):
    """Process a heart rate bpm JSON file from Fit/All Data/.
    Yields (timestamp_iso8601_utc, value) where value is heart rate in bpm.
    """
    with open(filepath, 'r') as f:
        data = json.load(f)
    if "Data Points" not in data:
        return
    for point in data["Data Points"]:
        if "fitValue" not in point or not point["fitValue"]:
            continue
        try:
            val = point["fitValue"][0]["value"]["fpVal"]
        except (KeyError, IndexError, TypeError):
            continue
        start_time_nanos = point.get("startTimeNanos")
        if start_time_nanos is None:
            continue
        timestamp = nanoseconds_to_iso8601utc(start_time_nanos)
        yield timestamp, val

def process_fit_all_data_weight(filepath):
    """Process a weight JSON file from Fit/All Data/.
    We'll look for body mass data. Might be in various formats.
    For simplicity, we'll assume it's similar to heart rate but with body mass.
    """
    with open(filepath, 'r') as f:
        data = json.load(f)
    if "Data Points" not in data:
        return
    for point in data["Data Points"]:
        if "fitValue" not in point or not point["fitValue"]:
            continue
        try:
            val = point["fitValue"][0]["value"]["fpVal"]
        except (KeyError, IndexError, TypeError):
            continue
        start_time_nanos = point.get("startTimeNanos")
        if start_time_nanos is None:
            continue
        timestamp = nanoseconds_to_iso8601utc(start_time_nanos)
        yield timestamp, val

def process_fit_interval_csv(filepath):
    """Process an interval CSV file from Fit/Daily activity metrics/.
    The filename contains the date (YYYY-MM-DD.csv).
    Each row is a 15-minute interval with a time of day and offset.
    Yields (timestamp_iso8601_utc, row_dict) for each row.
    """
    # Extract date from filename
    filename = os.path.basename(filepath)
    date_obj = parse_csv_interval_filename(filename)
    if date_obj is None:
        return
    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)  # Uses first row as fieldnames
        for row in reader:
            # Get the Start time column
            time_str = row.get('Start time')
            if not time_str:
                continue
            time_obj, offset_hours = parse_time_of_day(time_str)
            # Combine date and time to get UTC datetime
            utc_dt = combine_date_and_time(date_obj, time_obj, offset_hours)
            timestamp = utc_dt.isoformat()
            # Yield timestamp and the row dict
            yield timestamp, row

def process_google_health_daily(filepath):
    """Process a daily JSON file from Google Health/Global Export Data/.
    The filename contains the metric and date (e.g., calories-2023-10-02.json).
    The content is an array of objects with dateTime and value.
    We'll parse dateTime (MM/DD/YY HH:MM:SS) to datetime.
    We'll assume the time is in UTC and make it timezone-aware.
    """
    filename = os.path.basename(filepath)
    # Extract metric name and date from filename: e.g., "calories-2023-10-02.json"
    # We'll remove the extension and split on the first '-'
    basename = filename[:-5]  # remove .json
    if '-' not in basename:
        return
    metric, date_str = basename.split('-', 1)
    # Validate date_str format YYYY-MM-DD
    if not re.match(r'\d{4}-\d{2}-\d{2}$', date_str):
        return
    try:
        base_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return
    with open(filepath, 'r') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return
    if not isinstance(data, list):
        return
    for item in data:
        if not isinstance(item, dict):
            continue
        dt_str = item.get('dateTime')
        val_str = item.get('value')
        if not dt_str or not val_str:
            continue
        # Parse dt_str: MM/DD/YY HH:MM:SS
        try:
            # Note: year is two-digit
            dt = datetime.strptime(dt_str, "%m/%d/%y %H:%M:%S")
        except ValueError:
            continue
        # We'll assume dt is in UTC and make it timezone-aware.
        # If the time string had a timezone, we would have parsed it, but it doesn't.
        dt_utc = dt.replace(tzinfo=timezone.utc)
        timestamp = dt_utc.isoformat()
        # Convert value to float if possible, else keep string
        try:
            val = float(val_str)
        except ValueError:
            val = val_str
        yield timestamp, val

def write_csv_for_metric(metric_key, timestamp_value_pairs):
    """Write timestamp-value pairs to a CSV file for the given metric."""
    metric_info = METRICS[metric_key]
    output_file = os.path.join(OUTPUT_DIR, metric_info["output_file"])
    # Deduplicate by timestamp, keeping the last value encountered
    unique = {}
    for timestamp, value in timestamp_value_pairs:
        unique[timestamp] = value
    # Sort by timestamp
    sorted_pairs = sorted(unique.items(), key=lambda x: x[0])
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        # Write header
        writer.writerow(["timestamp", "value"])
        for timestamp, value in sorted_pairs:
            writer.writerow([timestamp, value])
    print(f"Written {len(sorted_pairs)} rows to {output_file}")

def process_sleep_analysis():
    """Process sleep data and write to sleep_analysis.csv."""
    # We'll output startDate, endDate, value (1 for asleep)
    output_file = os.path.join(OUTPUT_DIR, "sleep_analysis.csv")
    rows = []
    for filename in os.listdir(GOOGLE_HEALTH_DIR):
        if not re.match(r'^sleep-\d{4}-\d{2}-\d{2}\.json$', filename):
            continue
        filepath = os.path.join(GOOGLE_HEALTH_DIR, filename)
        with open(filepath, 'r') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                continue
        if not isinstance(data, list):
            continue
        for item in data:
            if not isinstance(item, dict):
                continue
            start_str = item.get('startTime')
            end_str = item.get('endTime')
            if not start_str or not end_str:
                continue
            # Parse startTime and endString: they are in ISO 8601 already?
            # Example: "2017-02-26T00:57:30.000"
            try:
                start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
            except ValueError:
                continue
            # Ensure timezone aware; if not, assume UTC
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)
            # Convert to ISO 8601 string
            start_iso = start_dt.isoformat()
            end_iso = end_dt.isoformat()
            # Value: 1 for asleep (HKCategoryValueSleepAnalysisAsleep)
            rows.append((start_iso, end_iso, 1))
    # Sort by start time
    rows.sort(key=lambda x: x[0])
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["startDate", "endDate", "value"])  # Note: changed to three columns
        for start, end, value in rows:
            writer.writerow([start, end, value])
    print(f"Written {len(rows)} rows to {output_file}")

def main():
    print("Starting data preparation for Apple Health import...")
    print(f"Output directory: {OUTPUT_DIR}")

    # Process each metric except sleep (handled separately)
    for metric_key in METRICS:
        if metric_key == "sleep_analysis":
            continue
        print(f"\nProcessing metric: {metric_key} ({METRICS[metric_key]['description']})")
        # Collect all timestamp-value pairs from all sources
        pairs = []
        # First, try to get data from Fit/All Data/ if applicable
        # Then from interval CSV, then from Google Health daily.
        # We'll just use the generic source processing for now, but we need to handle interval CSV specially.
        # Let's handle interval CSV separately for metrics that need it.
        # For now, we'll process all sources as defined, but we need to adjust for interval CSV.
        # We'll skip interval CSV in the generic loop and handle it per metric below.
        # We'll create a list of sources excluding interval CSV for the generic processing.
        non_interval_sources = []
        interval_sources = []
        for source_dir, pattern, source_type, skip_if in METRICS[metric_key]["sources"]:
            if source_type == "fit_interval_csv":
                interval_sources.append((source_dir, pattern, source_type, skip_if))
            else:
                non_interval_sources.append((source_dir, pattern, source_type, skip_if))
        # Process non-interval sources
        for source_dir, pattern, source_type, skip_if in non_interval_sources:
            regex = re.compile(pattern)
            for filename in os.listdir(source_dir):
                if regex.match(filename):
                    # Skip if any of the skip_if substrings are in filename (case-insensitive)
                    if any(substr.lower() in filename.lower() for substr in skip_if):
                        continue
                    filepath = os.path.join(source_dir, filename)
                    if source_type == "fit_all_data_step_delta":
                        for timestamp, value in process_fit_all_data_step_delta(filepath):
                            pairs.append((timestamp, value))
                    elif source_type == "fit_all_data_heart_rate":
                        for timestamp, value in process_fit_all_data_heart_rate(filepath):
                            pairs.append((timestamp, value))
                    elif source_type == "fit_all_data_weight":
                        for timestamp, value in process_fit_all_data_weight(filepath):
                            pairs.append((timestamp, value))
                    elif source_type == "google_health_daily":
                        for timestamp, value in process_google_health_daily(filepath):
                            pairs.append((timestamp, value))
                    elif source_type == "fit_all_data_body_fat":
                        # We skip body fat for body_mass, but just in case
                        pass
                    else:
                        print(f"Unknown source type: {source_type} for file {filename}")
        # Process interval CSV sources if any
        if interval_sources:
            # For each interval CSV file, we need to extract the appropriate column.
            # We'll map metric to column name in the CSV.
            column_map = {
                "distance": "Distance (m)",
                "active_energy": "Calories (kcal)",
                # Add others if needed
            }
            target_column = column_map.get(metric_key)
            if target_column is None:
                print(f"No column mapping for metric {metric_key} in interval CSV; skipping.")
            else:
                for source_dir, pattern, source_type, skip_if in interval_sources:
                    regex = re.compile(pattern)
                    for filename in os.listdir(source_dir):
                        if regex.match(filename):
                            # Skip if any of the skip_if substrings are in filename (case-insensitive)
                            if any(substr.lower() in filename.lower() for substr in skip_if):
                                continue
                            filepath = os.path.join(source_dir, filename)
                            for timestamp, row in process_fit_interval_csv(filepath):
                                value_str = row.get(target_column)
                                if value_str is None or value_str == '':
                                    continue
                                try:
                                    value = float(value_str)
                                except ValueError:
                                    continue
                                pairs.append((timestamp, value))
        # Write CSV for this metric
        if pairs:
            write_csv_for_metric(metric_key, pairs)
        else:
            print(f"No data found for metric {metric_key}")

    # Process sleep analysis separately
    print("\nProcessing sleep analysis...")
    process_sleep_analysis()

    print("\nDone!")

if __name__ == "__main__":
    main()