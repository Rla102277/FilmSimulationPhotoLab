import Foundation
import ImageCaptureCore
import IALUTCore

@main
struct Q3TestMain {
    @MainActor
    static func main() async {
        let args = Array(CommandLine.arguments.dropFirst())
        let command = args.first ?? "help"

        print("Infinite Arch Leica Q3 USB/PTP Test Harness")
        print("Q3: USB mode PTP · Quit Image Capture before testing")
        print("")

        do {
            switch command {
            case "probe":
                print("Probing Q3 USB/PTP…")
                print(try await USBQ3Bridge.shared.probe())

            case "list":
                print("Reading Leica Look list…")
                print(try await USBQ3Bridge.shared.readLookPropertyList())

            case "silver":
                print("WARNING: this performs one Leica Look write using official Silver ID 24.")
                print("Sending…")
                print(try await USBQ3Bridge.shared.installMVPOfficialSilver())

            case "identity":
                print("WARNING: this performs one Leica Look write using Leica Cine ID 27 with a neutral LUT.")
                print("Sending…")
                print(try await USBQ3Bridge.shared.installMVPCustomIdentity())

            case "pairing-on":
                print("Setting Leica SDK Bluetooth pairing ON using native-derived 0x902D [2,1]…")
                print(try await USBQ3Bridge.shared.setSDKPairing(true))

            case "pairing-off":
                print("Setting Leica SDK Bluetooth pairing OFF using native-derived 0x902D [3,1]…")
                print(try await USBQ3Bridge.shared.setSDKPairing(false))

            case "pairing-silver":
                print("Running native-derived pairing + remote + official Silver test…")
                print("Sequence: 0x9005 -> 0x902D [2,1] -> 0x9030 [0,1] -> 0x9035 -> 0x902D [3,1]")
                print(try await USBQ3Bridge.shared.installPairingAuthorizedSilver())

            case "prop-desc":
                print("Read-only PTP descriptors for Leica properties D69C/D69D…")
                print(try await USBQ3Bridge.shared.probeRemotePropertyDescriptors())

            case "state-probe":
                print("Read-only Leica remote-state property probe…")
                print(try await USBQ3Bridge.shared.probeRemoteStateProperties())

            case "remote-on":
                print("Setting Leica SDK remote status ON using native-derived 0x9030 [0,1]…")
                print(try await USBQ3Bridge.shared.setSDKRemoteStatus(true))

            case "remote-off":
                print("Setting Leica SDK remote status OFF using native-derived 0x9030 [0,0]…")
                print(try await USBQ3Bridge.shared.setSDKRemoteStatus(false))

            case "authorized-silver":
                print("Running one-session authorization + official Silver upload…")
                print("Sequence: 0x9005 -> 0x9030 [0,1] -> 0x9035")
                print(try await USBQ3Bridge.shared.installAuthorizedSilver())

            case "all-read":
                print("1/2 USB/PTP probe")
                print(try await USBQ3Bridge.shared.probe())
                print("")
                print("2/2 Leica Look list")
                print(try await USBQ3Bridge.shared.readLookPropertyList())

            case "ip-access":
                let clientID=args.dropFirst().first ?? "89440BC7-DFC6-4929-A68D-8BD1C3C47BDF"
                print("Checking the Q3 Wi-Fi access gate (no camera settings or Looks are changed)…")
                let q3=DirectQ3Transport()
                print(try await q3.requestAccess(clientID:clientID))

            case "ip-read":
                print("Reading the Leica Look table over PTP/IP without changing HTTP access state…")
                let q3=DirectQ3Transport()
                print(try await q3.readOnlyLookProbe())

            case "help", "--help", "-h":
                usage()

            default:
                print("Unknown command: \(command)")
                print("")
                usage()
                Foundation.exit(2)
            }
        } catch {
            print("ERROR: \(error.localizedDescription)")
            Foundation.exit(1)
        }
    }

    static func usage() {
        print("""
        Usage:
          swift run q3test probe
          swift run q3test list
          swift run q3test all-read
          swift run q3test ip-access [FOTOS-client-UUID]
          swift run q3test ip-read [FOTOS-client-UUID]
          swift run q3test state-probe
          swift run q3test prop-desc
          swift run q3test pairing-on
          swift run q3test pairing-off
          swift run q3test pairing-silver
          swift run q3test remote-on
          swift run q3test remote-off
          swift run q3test authorized-silver
          swift run q3test silver
          swift run q3test identity

        Read-only:
          probe      Verify USB PTP and Leica vendor ops
          list       Read/decode Q3 Leica Look table
          all-read   Run both read-only tests
          ip-access  Replay captured FOTOS access request and report open/encrypted state
          ip-read    Leave HTTP access untouched and try the read-only network 0x9033 query

        Session-state research:
          state-probe    Read D69C/D69D before/after remote enable
          prop-desc      Read PTP descriptors for D69C/D69D
          pairing-on     Native Leica enablePairing: 0x902D [2,1]
          pairing-off    Native Leica disablePairing: 0x902D [3,1]
          pairing-silver Pairing + remote + official Silver, then pairing cleanup
          remote-on   Set Leica SDK RemoteFunction 0 / RemoteStatus 1 via 0x9030
          remote-off  Restore Leica SDK RemoteFunction 0 / RemoteStatus 0 via 0x9030

        Writes (run only when intentionally testing):
          authorized-silver  Enable Leica SDK remote state and upload official Silver in ONE PTP session
          silver     Official Leica Silver payload, ID 24
          identity   Neutral 17^3 LUT under known Leica Cine ID 27

        Current known write behavior:
          0x9035 over USB returns 0x200F (Access Denied) on this Q3.
        """)
    }
}
