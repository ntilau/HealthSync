import SwiftUI
import HealthKit

struct HealthDataView: View {
    @StateObject private var viewModel = HealthDataViewModel()

    var body: some View {
        NavigationView {
            VStack(spacing: 20) {
                if !HealthKitManager.isHealthKitAvailable() {
                    VStack {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .font(.largeTitle)
                            .foregroundColor(.orange)
                        Text("HealthKit is not available on this device")
                            .multilineTextAlignment(.center)
                            .padding()
                    }
                    .padding()
                } else {
                    Form {
                        Section(header: Text("Authorization")) {
                            Button(viewModel.isAuthorized ? "Refresh Authorization" : "Request HealthKit Access") {
                                viewModel.requestAuthorization()
                            }
                            .buttonStyle(.borderedProminent)

                            if viewModel.isAuthorized {
                                Text("Authorized to read health data")
                                    .foregroundColor(.green)
                            } else if viewModel.authorizationStatus == .notDetermined {
                                Text("Authorization not yet requested")
                                    .foregroundColor(.secondary)
                            } else {
                                Text("Authorization denied")
                                    .foregroundColor(.red)
                            }
                        }

                        Section(header: Text("Data Fetching")) {
                            DatePicker("Start Date", selection: $viewModel.startDate, displayedComponents: .date)
                            DatePicker("End Date", selection: $viewModel.endDate, displayedComponents: .date)

                            Button(viewModel.isFetching ? "Fetching..." : "Fetch Health Data") {
                                viewModel.fetchHealthData()
                            }
                            .buttonStyle(.borderedProminent)
                            .disabled(!viewModel.isAuthorized || viewModel.isFetching)
                        }

                        if !viewModel.fetchedData.isEmpty {
                            Section(header: Text("Fetched Data")) {
                                ForEach(viewModel.fetchedData.keys.sorted { $0.rawValue < $1.rawValue }, id: \.self) { type in
                                    if let samples = viewModel.fetchedData[type], !samples.isEmpty {
                                        DisclosureGroup("\(type.rawValue): \(samples.count) samples") {
                                            Text("First sample: \(formatSample(samples.first!))")
                                                .font(.caption)
                                                .foregroundColor(.secondary)
                                        }
                                    }
                                }
                            }

                            Section(header: Text("Export")) {
                                Button("Export to CSV") {
                                    viewModel.exportData()
                                }
                                .buttonStyle(.bordered)
                                .disabled(viewModel.fetchedData.isEmpty)

                                if let exportMessage = viewModel.exportMessage {
                                    Text(exportMessage)
                                        .font(.caption)
                                        .foregroundColor(viewModel.exportSuccess ? .green : .red)
                                        .padding(.vertical, 4)
                                }
                            }
                        }
                    }
                }
            }
            .navigationTitle("Apple Health Data Importer")
            .padding()
        }
    }

    private func formatSample(_ sample: HealthDataSample) -> String {
        let formatter = DateFormatter()
        formatter.dateStyle = .short
        formatter.timeStyle = .short
        let dateString = formatter.string(from: sample.timestamp)
        return "\(dateString): \(sample.value) \(sample.unit)"
    }
}

class HealthDataViewModel: ObservableObject {
    @Published var isAuthorized = false
    @Published var authorizationStatus: HKAuthorizationStatus = .notDetermined
    @Published var isFetching = false
    @Published var fetchedData: [HealthDataType: [HealthDataSample]] = [:]
    @Published var exportMessage = ""
    @Published var exportSuccess = false

    var startDate = Date().addingTimeInterval(-86400 * 7) // Last 7 days
    var endDate = Date()

    func requestAuthorization() {
        HealthKitManager.shared.requestAuthorization { [weak self] success, error in
            DispatchQueue.main.async {
                self?.isAuthorized = success
                self?.authorizationStatus = success ? .sharingAuthorized : .sharingDenied
                if let error = error {
                    print("Authorization error: \(error.localizedDescription)")
                }
            }
        }
    }

    func fetchHealthData() {
        guard !isFetching else { return }
        isFetching = true
        fetchedData.removeAll()

        let group = DispatchGroup()

        // Fetch each data type
        for type in [HealthDataType.stepCount, .distance, .heartRate, .activeEnergy, .bodyMass, .height, .sleepAnalysis] {
            group.enter()

            switch type {
            case .stepCount:
                HealthKitManager.shared.fetchStepCount(startDate: startDate, endDate: endDate) { [weak self] samples, error in
                    if let error = error {
                        print("Step count error: \(error.localizedDescription)")
                    } else {
                        self?.fetchedData[type] = samples.map { $0.toHealthDataSample() }
                    }
                    group.leave()
                }

            case .distance:
                HealthKitManager.shared.fetchDistance(startDate: startDate, endDate: endDate) { [weak self] samples, error in
                    if let error = error {
                        print("Distance error: \(error.localizedDescription)")
                    } else {
                        self?.fetchedData[type] = samples.map { $0.toHealthDataSample() }
                    }
                    group.leave()
                }

            case .heartRate:
                HealthKitManager.shared.fetchHeartRate(startDate: startDate, endDate: endDate) { [weak self] samples, error in
                    if let error = error {
                        print("Heart rate error: \(error.localizedDescription)")
                    } else {
                        self?.fetchedData[type] = samples.map { $0.toHealthDataSample() }
                    }
                    group.leave()
                }

            case .activeEnergy:
                HealthKitManager.shared.fetchActiveEnergy(startDate: startDate, endDate: endDate) { [weak self] samples, error in
                    if let error = error {
                        print("Active energy error: \(error.localizedDescription)")
                    } else {
                        self?.fetchedData[type] = samples.map { $0.toHealthDataSample() }
                    }
                    group.leave()
                }

            case .bodyMass:
                HealthKitManager.shared.fetchBodyMass(startDate: startDate, endDate: endDate) { [weak self] samples, error in
                    if let error = error {
                        print("Body mass error: \(error.localizedDescription)")
                    } else {
                        self?.fetchedData[type] = samples.map { $0.toHealthDataSample() }
                    }
                    group.leave()
                }

            case .height:
                HealthKitManager.shared.fetchHeight(startDate: startDate, endDate: endDate) { [weak self] samples, error in
                    if let error = error {
                        print("Height error: \(error.localizedDescription)")
                    } else {
                        self?.fetchedData[type] = samples.map { $0.toHealthDataSample() }
                    }
                    group.leave()
                }

            case .sleepAnalysis:
                HealthKitManager.shared.fetchSleepAnalysis(startDate: startDate, endDate: endDate) { [weak self] samples, error in
                    if let error = error {
                        print("Sleep analysis error: \(error.localizedDescription)")
                    } else {
                        self?.fetchedData[type] = samples.map { $0.toHealthDataSample() }
                    }
                    group.leave()
                }
            }
        }

        group.notify(queue: .main) { [weak self] in
            self?.isFetching = false
            self?.objectWillChange.send()
        }
    }

    func exportData() {
        guard !fetchedData.isEmpty else {
            exportMessage = "No data to export"
            exportSuccess = false
            return
        }

        let fileManager = FileManager.default
        let documentDirectory = fileManager.urls(for: .documentDirectory, in: .userDomainMask).first!
        let exportDirectory = documentDirectory.appendingPathComponent("AppleHealthExport")

        do {
            try DataExportService.shared.exportAllHealthData(fetchedData, to: exportDirectory)
            exportMessage = "Data exported successfully to \(exportDirectory.path)"
            exportSuccess = true
        } catch {
            exportMessage = "Export failed: \(error.localizedDescription)"
            exportSuccess = false
        }
    }
}

// MARK: - ISO8601 Date Formatter Extension

extension ISO8601DateFormatter {
    convenience init(timeZone: TimeZone, format: Options) {
        self.init()
        self.timeZone = timeZone
        self.formatOptions = format
    }

    static func string(from date: Date, timeZone: TimeZone, format: Options) -> String {
        let formatter = ISO8601DateFormatter(timeZone: timeZone, format: format)
        return formatter.string(from: date)
    }
}