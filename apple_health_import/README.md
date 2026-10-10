# Apple Health Import Data

This directory contains CSV files prepared from Google Takeout data (Fit and Google Health) for import into Apple Health.

## Files

- `step_count.csv`: Step count deltas (steps per 15-minute interval). To get cumulative steps, the importing tool should accumulate the deltas over time.
- `distance.csv`: Distance moved in meters.
- `active_energy.csv`: Active energy burned in kilocalories (kcal).
- `heart_rate.csv`: Heart rate in beats per minute (bpm).
- `body_mass.csv`: Body mass in kilograms (kg).
- `height.csv`: Height in meters (m).
- `sleep_analysis.csv`: Sleep analysis with start date, end date, and value (1 = asleep).

## Format

All CSV files (except sleep_analysis.csv) have two columns:
- `timestamp`: ISO 8601 format in UTC (e.g., "2026-09-08T00:00:00+00:00")
- `value`: Numeric value corresponding to the metric.

The `sleep_analysis.csv` has three columns:
- `startDate`: ISO 8601 timestamp in UTC indicating the start of the sleep period.
- `endDate`: ISO 8601 timestamp in UTC indicating the end of the sleep period.
- `value`: 1 indicating asleep (HKCategoryValueSleepAnalysisAsleep).

## Importing into Apple Health

To import this data into Apple Health, you can use a third-party app such as:
- [Health Importer](https://apps.apple.com/us/app/health-importer/id1455273301) (iOS)
- [QS Access](https://apps.apple.com/us/app/qs-access/id925316332) (iOS) - for exporting, but can also import via other means
- Alternatively, you can use a script or shortcut to add the data via HealthKit.

Please refer to the documentation of the chosen app for specific import instructions.

## Notes

- The timestamps are in UTC. If your device is in a different timezone, the importing tool may adjust the time accordingly.
- Some metrics may have missing data for certain periods due to limitations in the source data.
- Step count data is provided as deltas (steps per interval) because the source data provides step count deltas from Google Fit. To obtain cumulative step counts, accumulate the deltas in chronological order.
- Distance and active energy data are derived from the 15-minute interval CSV files in the Takeout data where available.
- Heart rate data is derived from granular heart rate bpm files in the Takeout data.
- Body mass data is derived from weight files in the Takeout data.
- Height and sleep data are derived from daily JSON files in the Google Health Takeout data.

## Generated on

$(date)

"""