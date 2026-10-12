import Foundation
import HealthKit

@MainActor class DataExportService {
    static let shared = DataExportService()
    private init() {}

    // Export health data samples to CSV format matching apple_health_import/ structure
    func exportHealthData(samples: [HealthDataSample], type: HealthDataType, to directory: URL) throws {
        // Ensure directory exists
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true, attributes: nil)

        let fileURL = directory.appendingPathComponent(type.csvFilename)

        // Prepare CSV content
        var csvContent = type.csvHeader + "\n"

        // Sort samples by timestamp
        let sortedSamples = samples.sorted { $0.timestamp < $1.timestamp }

        // For most types: timestamp,value
        // For sleep analysis: startDate,endDate,value (we'll use timestamp as startDate and approximate endDate)
        for sample in sortedSamples {
            let formatter = ISO8601DateFormatter()
            formatter.timeZone = TimeZone(secondsFromGMT: 0) // UTC
            formatter.formatOptions = .withInternetDateTime // equivalent to .extended
            let timestampString = formatter.string(from: sample.timestamp)

            switch type {
            case .sleepAnalysis:
                // For sleep analysis, we need start and end times
                // Since we only have timestamp from HealthKit, we'll use it as start
                // and add a small duration for end (this is a simplification)
                let endDate = sample.timestamp.addingTimeInterval(300) // 5 minutes later as placeholder
                let endTimestampString = formatter.string(from: endDate)
                csvContent += "\(timestampString),\(endTimestampString),\(Int(sample.value))\n"
            default:
                csvContent += "\(timestampString),\(sample.value)\n"
            }
        }

        // Write to file
        try csvContent.write(to: fileURL, atomically: true, encoding: .utf8)
    }

    // Export multiple data types at once
    func exportAllHealthData(_ dataByType: [HealthDataType: [HealthDataSample]], to directory: URL) throws {
        for (type, samples) in dataByType {
            try exportHealthData(samples: samples, type: type, to: directory)
        }
    }
}