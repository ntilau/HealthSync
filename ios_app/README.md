# Apple Health Data Importer

This iOS application allows you to read data from Apple Health (HealthKit) and export it in CSV format compatible with the existing `apple_health_import/` directory structure in this repository.

## Features

- Request authorization to read various health data types from Apple Health
- Fetch health data samples for a specified date range
- Supported data types:
  - Step count
  - Distance walked/run
  - Heart rate
  - Active energy burned
  - Body mass
  - Height
  - Sleep analysis
- Export data to CSV files matching the format used by `prepare_apple_health_data.py`
- Simple SwiftUI interface for easy interaction

## Data Types Exported

The app exports the following CSV files (matching the format from `apple_health_import/`):

1. `step_count.csv` - `timestamp,value` (steps as integer)
2. `distance.csv` - `timestamp,value` (distance in meters)
3. `heart_rate.csv` - `timestamp,value` (heart rate in bpm)
4. `active_energy.csv` - `timestamp,value` (energy in kilocalories)
5. `body_mass.csv` - `timestamp,value` (mass in kilograms)
6. `height.csv` - `timestamp,value` (height in centimeters)
7. `sleep_analysis.csv` - `startDate,endDate,value` (value = 1 for asleep, 0 for awake)

All timestamps are in ISO 8601 UTC format for consistency with the existing repository tools.

## Usage

1. Build and run the app on your iOS device (requires iOS 8.0+ with HealthKit)
2. On first launch, tap "Request HealthKit Access" to authorize data reading
3. Select the date range for data you want to fetch
4. Tap "Fetch Health Data" to retrieve data from Apple Health
5. Review the fetched data counts for each type
6. Tap "Export to CSV" to save the data to your device's Documents/AppleHealthExport directory
7. Transfer the exported CSV files to your computer and place them in the `apple_health_import/` directory to use with existing repository tools

## Requirements

- iOS 8.0 or later
- Device with HealthKit capabilities (iPhone)
- Xcode 11.0+ or Swift Playgrounds for building
- HealthKit permission granted

## Building the App

1. Open the `ios_app` directory in Xcode
2. Select your development team in the Signing & Capabilities tab
3. Build and run on a connected iOS device
4. Note: The simulator has limited HealthKit data availability

## Integration with Existing Repository

The exported CSV files are formatted to match exactly what the `prepare_apple_health_data.py` script produces, allowing seamless integration:

- Same column headers and structure
- Same ISO 8601 UTC timestamp format
- Same value formatting and units
- Same file naming convention

This enables you to:
1. Export data from Apple Health using this iOS app
2. Import the CSV files into the `apple_health_import/` directory
3. Use existing repository tools to analyze or synchronize the data