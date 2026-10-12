import HealthKit

@MainActor class HealthKitManager {
    static let shared = HealthKitManager()
    let healthStore = HKHealthStore()

    private init() {}

    // Request authorization to read health data
    func requestAuthorization(completion: @escaping (Bool, Error?) -> Void) {
        // Define the data types we want to read
        let typesToRead: Set<HKObjectType> = [
            HKObjectType.quantityType(forIdentifier: .stepCount)!,
            HKObjectType.quantityType(forIdentifier: .distanceWalkingRunning)!,
            HKObjectType.quantityType(forIdentifier: .heartRate)!,
            HKObjectType.quantityType(forIdentifier: .activeEnergyBurned)!,
            HKObjectType.quantityType(forIdentifier: .bodyMass)!,
            HKObjectType.quantityType(forIdentifier: .height)!,
            HKObjectType.categoryType(forIdentifier: .sleepAnalysis)!
        ]

        // Request authorization
        healthStore.requestAuthorization(toShare: nil, read: typesToRead) { (success, error) in
            completion(success, error)
        }
    }

    // Check if HealthKit is available
    class func isHealthKitAvailable() -> Bool {
        return HKHealthStore.isHealthDataAvailable()
    }

    // Fetch step count data
    func fetchStepCount(startDate: Date, endDate: Date, completion: @escaping ([HKQuantitySample], Error?) -> Void) {
        guard let stepType = HKQuantityType.quantityType(forIdentifier: .stepCount) else {
            completion([], NSError(domain: "HealthKitManager", code: -1, userInfo: [NSLocalizedDescriptionKey: "Unable to create step count type"]))
            return
        }

        let predicate = HKQuery.predicateForSamples(withStart: startDate, end: endDate, options: .strictStartDate)
        let query = HKSampleQuery(sampleType: stepType, predicate: predicate, limit: HKObjectQueryNoLimit, sortDescriptors: nil) { (query, samples, error) in
            completion(samples as? [HKQuantitySample] ?? [], error)
        }

        healthStore.execute(query)
    }

    // Fetch distance data
    func fetchDistance(startDate: Date, endDate: Date, completion: @escaping ([HKQuantitySample], Error?) -> Void) {
        guard let distanceType = HKQuantityType.quantityType(forIdentifier: .distanceWalkingRunning) else {
            completion([], NSError(domain: "HealthKitManager", code: -1, userInfo: [NSLocalizedDescriptionKey: "Unable to create distance type"]))
            return
        }

        let predicate = HKQuery.predicateForSamples(withStart: startDate, end: endDate, options: .strictStartDate)
        let query = HKSampleQuery(sampleType: distanceType, predicate: predicate, limit: HKObjectQueryNoLimit, sortDescriptors: nil) { (query, samples, error) in
            completion(samples as? [HKQuantitySample] ?? [], error)
        }

        healthStore.execute(query)
    }

    // Fetch heart rate data
    func fetchHeartRate(startDate: Date, endDate: Date, completion: @escaping ([HKQuantitySample], Error?) -> Void) {
        guard let heartRateType = HKQuantityType.quantityType(forIdentifier: .heartRate) else {
            completion([], NSError(domain: "HealthKitManager", code: -1, userInfo: [NSLocalizedDescriptionKey: "Unable to create heart rate type"]))
            return
        }

        let predicate = HKQuery.predicateForSamples(withStart: startDate, end: endDate, options: .strictStartDate)
        let query = HKSampleQuery(sampleType: heartRateType, predicate: predicate, limit: HKObjectQueryNoLimit, sortDescriptors: nil) { (query, samples, error) in
            completion(samples as? [HKQuantitySample] ?? [], error)
        }

        healthStore.execute(query)
    }

    // Fetch active energy data
    func fetchActiveEnergy(startDate: Date, endDate: Date, completion: @escaping ([HKQuantitySample], Error?) -> Void) {
        guard let activeEnergyType = HKQuantityType.quantityType(forIdentifier: .activeEnergyBurned) else {
            completion([], NSError(domain: "HealthKitManager", code: -1, userInfo: [NSLocalizedDescriptionKey: "Unable to create active energy type"]))
            return
        }

        let predicate = HKQuery.predicateForSamples(withStart: startDate, end: endDate, options: .strictStartDate)
        let query = HKSampleQuery(sampleType: activeEnergyType, predicate: predicate, limit: HKObjectQueryNoLimit, sortDescriptors: nil) { (query, samples, error) in
            completion(samples as? [HKQuantitySample] ?? [], error)
        }

        healthStore.execute(query)
    }

    // Fetch body mass data
    func fetchBodyMass(startDate: Date, endDate: Date, completion: @escaping ([HKQuantitySample], Error?) -> Void) {
        guard let bodyMassType = HKQuantityType.quantityType(forIdentifier: .bodyMass) else {
            completion([], NSError(domain: "HealthKitManager", code: -1, userInfo: [NSLocalizedDescriptionKey: "Unable to create body mass type"]))
            return
        }

        let predicate = HKQuery.predicateForSamples(withStart: startDate, end: endDate, options: .strictStartDate)
        let query = HKSampleQuery(sampleType: bodyMassType, predicate: predicate, limit: HKObjectQueryNoLimit, sortDescriptors: nil) { (query, samples, error) in
            completion(samples as? [HKQuantitySample] ?? [], error)
        }

        healthStore.execute(query)
    }

    // Fetch height data
    func fetchHeight(startDate: Date, endDate: Date, completion: @escaping ([HKQuantitySample], Error?) -> Void) {
        guard let heightType = HKQuantityType.quantityType(forIdentifier: .height) else {
            completion([], NSError(domain: "HealthKitManager", code: -1, userInfo: [NSLocalizedDescriptionKey: "Unable to create height type"]))
            return
        }

        let predicate = HKQuery.predicateForSamples(withStart: startDate, end: endDate, options: .strictStartDate)
        let query = HKSampleQuery(sampleType: heightType, predicate: predicate, limit: HKObjectQueryNoLimit, sortDescriptors: nil) { (query, samples, error) in
            completion(samples as? [HKQuantitySample] ?? [], error)
        }

        healthStore.execute(query)
    }

    // Fetch sleep analysis data
    func fetchSleepAnalysis(startDate: Date, endDate: Date, completion: @escaping ([HKCategorySample], Error?) -> Void) {
        guard let sleepType = HKObjectType.categoryType(forIdentifier: .sleepAnalysis) else {
            completion([], NSError(domain: "HealthKitManager", code: -1, userInfo: [NSLocalizedDescriptionKey: "Unable to create sleep analysis type"]))
            return
        }

        let predicate = HKQuery.predicateForSamples(withStart: startDate, end: endDate, options: .strictStartDate)
        let query = HKSampleQuery(sampleType: sleepType, predicate: predicate, limit: HKObjectQueryNoLimit, sortDescriptors: nil) { (query, samples, error) in
            completion(samples as? [HKCategorySample] ?? [], error)
        }

        healthStore.execute(query)
    }
}