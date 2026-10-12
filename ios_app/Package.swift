// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "HealthImportApp",
    platforms: [
        .macOS(.v13)
    ],
    products: [
        .executable(
            name: "HealthImportApp",
            targets: ["HealthImportApp"])
    ],
    dependencies: [],
    targets: [
        .executableTarget(
            name: "HealthImportApp",
            dependencies: [],
            path: ".",
            sources: [
                "HealthImportApp.swift",
                "HealthDataView.swift", 
                "HealthDataModel.swift",
                "HealthKitManager.swift",
                "DataExportService.swift",
                "main.swift"
            ])
    ]
)
