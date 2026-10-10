import Foundation
import HealthKit

// MARK: - Data Models

struct HealthDataSample {
    let timestamp: Date
    let value: Double
    let unit: String
    let metadata: [String: Any]?

    init(timestamp: Date, value: Double, unit: String, metadata: [String: Any]? = nil) {
        self.timestamp = timestamp
        self.value = value
        self.unit = unit
        self.metadata = metadata
    }
}

// MARK: - HealthKit Extensions

extension HKQuantitySample {
    func toHealthDataSample() -> HealthDataSample {
        return HealthDataSample(
            timestamp: self.startDate,
            value: self.quantity.doubleValue(for: self.quantity.unit),
            unit: self.quantity.unit.unitString,
            metadata: self.metadata
        )
    }
}

extension HKCategorySample {
    func toHealthDataSample() -> HealthDataSample {
        // For sleep analysis, value is 1.0 for asleep, 0.0 for awake
        let value = self.value == HKCategoryValueSleepAnalysis.asleep.rawValue ? 1.0 : 0.0
        return HealthDataSample(
            timestamp: self.startDate,
            value: value,
            unit: "count", // Sleep analysis uses integer values
            metadata: self.metadata
        )
    }
}

// MARK: - Unit String Extensions

extension HKUnit {
    var unitString: String {
        switch self {
        case HKUnit.count():
            return "count"
        case HKUnit.meter():
            return "m"
        case HKUnit.joule():
            return "J"
        case HKUnit.kilocalorie():
            return "kcal"
        case HKUnit.fromString("bpm"):
            return "bpm"
        case HKUnit.gramUnit(with: .kilo):
            return "kg"
        case HKUnit.meterUnit(with: .centi):
            return "cm"
        default:
            return self.description
        }
    }
}

// MARK: - Type Identifiers

enum HealthDataType {
    case stepCount
    case distance
    case heartRate
    case activeEnergy
    case bodyMass
    case height
    case sleepAnalysis

    var hkType: HKObjectType {
        switch self {
        case .stepCount:
            return HKObjectType.quantityType(forIdentifier: .stepCount)!
        case .distance:
            return HKObjectType.quantityType(forIdentifier: .distanceWalkingRunning)!
        case .heartRate:
            return HKObjectType.quantityType(forIdentifier: .heartRate)!
        case .activeEnergy:
            return HKObjectType.quantityType(forIdentifier: .activeEnergyBurned)!
        case .bodyMass:
            return HKObjectType.quantityType(forIdentifier: .bodyMass)!
        case .height:
            return HKObjectType.quantityType(forIdentifier: .height)!
        case .sleepAnalysis:
            return HKObjectType.categoryType(forIdentifier: .sleepAnalysis)!
        }
    }

    var csvFilename: String {
        switch self {
        case .stepCount:
            return "step_count.csv"
        case .distance:
            return "distance.csv"
        case .heartRate:
            return "heart_rate.csv"
        case .activeEnergy:
            return "active_energy.csv"
        case .bodyMass:
            return "body_mass.csv"
        case .height:
            return "height.csv"
        case .sleepAnalysis:
            return "sleep_analysis.csv"
        }
    }

    var csvHeader: String {
        switch self {
        case .sleepAnalysis:
            return "startDate,endDate,value"
        default:
            return "timestamp,value"
        }
    }
}