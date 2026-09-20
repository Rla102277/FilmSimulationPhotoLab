// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "InfiniteArchLeicaLookBuilder",
    platforms: [.macOS(.v13)],
    products: [
        .library(name: "IALUTCore", targets: ["IALUTCore"]),
        .executable(name: "InfiniteArchLeicaLookBuilder", targets: ["InfiniteArchLeicaLookBuilder"]),
        .executable(name: "ialut", targets: ["ialut"]),
        .executable(name: "q3test", targets: ["q3test"])
    ],
    targets: [
        .target(name: "IALUTCore"),
        .executableTarget(name: "InfiniteArchLeicaLookBuilder", dependencies: ["IALUTCore"], resources: [.copy("Resources")]),
        .executableTarget(name: "ialut", dependencies: ["IALUTCore"]),
        .executableTarget(name: "q3test", dependencies: ["IALUTCore"], resources: [.copy("Resources")]),
        .testTarget(name: "IALUTCoreTests", dependencies: ["IALUTCore"])
    ]
)
