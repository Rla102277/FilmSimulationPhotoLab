import Foundation

@main
struct Q3NetworkProbeMain {
    static let capturedClientID="89440BC7-DFC6-4929-A68D-8BD1C3C47BDF"

    static func main() async {
        let args=Array(CommandLine.arguments.dropFirst())
        let command=args.first ?? "help"
        let clientID=args.dropFirst().first ?? capturedClientID
        let q3=DirectQ3Transport()

        do {
            switch command {
            case "access":
                print("Q3 Wi-Fi access check (no camera settings or Looks are changed)")
                let report=try await q3.requestAccess(clientID:clientID)
                print(report)
                if report.finalResponse.contains("err_others_requesting") {
                    print("STOP: another access request is pending. Exit the Q3 connection mode before testing again.")
                } else if report.finalResponse.contains("err_critical") {
                    print("STOP: the access state machine needs to be reset by exiting the Q3 connection mode.")
                } else if report.finalResponse.contains("under_research_no_msg") {
                    print("STOP: this identity requires the missing encrypted pairing step; do not repeat this request.")
                }
            case "read":
                print("Direct read-only Leica Look table check (no HTTP access request)")
                print(try await q3.readOnlyLookProbe())
            case "handoff-read":
                let timeout=max(10,min(Int(args.dropFirst().first ?? "120") ?? 120,600))
                print("Waiting up to \(timeout)s for FOTOS to release the Q3 PTP listener")
                print("Now force-quit FOTOS on the iPhone; keep the Q3 connection screen open.")
                let deadline=Date().addingTimeInterval(TimeInterval(timeout))
                var attempts=0
                var lastError=""
                while Date()<deadline {
                    attempts+=1
                    do {
                        let result=try await q3.readOnlyLookProbe()
                        print("HANDOFF SUCCESS after \(attempts) attempts")
                        print(result)
                        return
                    } catch {
                        let message=error.localizedDescription
                        if message != lastError {
                            print("waiting: \(message)")
                            lastError=message
                        }
                    }
                    try await Task.sleep(nanoseconds:750_000_000)
                }
                print("HANDOFF TIMEOUT: the Q3 never opened its PTP listener to this Mac.")
                Foundation.exit(1)
            case "help","--help","-h":
                print("""
                Usage:
                  q3-network-probe access [FOTOS-client-UUID]
                  q3-network-probe read
                  q3-network-probe handoff-read [timeout-seconds]

                access  Checks whether the Q3 grants the captured FOTOS client open access.
                read    Does not request access; it only tries PTP/IP operation 0x9033.
                handoff-read
                         Waits for FOTOS to release its one PTP connection, then immediately
                         performs only the read-only 0x9033 query (default timeout: 120s).

                Both commands are read-only with respect to camera settings and Leica Looks.
                """)
            default:
                print("Unknown command: \(command)")
                Foundation.exit(2)
            }
        } catch {
            print("ERROR: \(error.localizedDescription)")
            Foundation.exit(1)
        }
    }
}
