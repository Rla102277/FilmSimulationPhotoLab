import SwiftUI
import Foundation
import AppKit
import UniformTypeIdentifiers
import IALUTCore

@main
struct AppMain:App {
    var body:some Scene { WindowGroup { BuilderView().frame(minWidth:1120,minHeight:760) } }
}

@MainActor
final class AppModel:ObservableObject {
    @Published var library:[URL]=[]
    @Published var selectedSource:URL?
    @Published var selectedLUT:LUT3D?
    @Published var recipe=InfiniteArchRecipe.defaults[4]
    @Published var outputName="Presence"
    @Published var sourceFolder:URL?
    @Published var status="Choose a LUT pack folder."
    @Published var slots:[LookSlot]=[]
    @Published var search=""
    @Published var cameraHost="192.168.54.1"
    @Published var cameraPort="15740"
    @Published var useUSB=true
    @Published var lookID:Int=1001
    @Published var q3Busy=false

    func indexFolder(_ folder:URL) {
        sourceFolder=folder
        let keys:[URLResourceKey]=[.isRegularFileKey]
        let en=FileManager.default.enumerator(at:folder,includingPropertiesForKeys:keys,options:[.skipsHiddenFiles])
        library=(en?.allObjects as? [URL] ?? []).filter { $0.pathExtension.lowercased() == "cube" }.sorted{$0.lastPathComponent.localizedCaseInsensitiveCompare($1.lastPathComponent) == .orderedAscending}
        status="Indexed \(library.count) .cube LUTs."
    }

    func load(_ url:URL) {
        do { selectedLUT=try CubeIO.read(url:url); selectedSource=url; status="Loaded \(url.lastPathComponent)." }
        catch { status=error.localizedDescription }
    }

    var filtered:[URL] { search.isEmpty ? library : library.filter{$0.lastPathComponent.localizedCaseInsensitiveContains(search)} }

    func addSlot() {
        guard let src=selectedSource, slots.count<9 else { return }
        let next=(1...9).first{ n in !slots.contains(where:{$0.slot == n}) } ?? 1
        slots.append(LookSlot(slot:next,name:outputName,sourcePath:src.path,recipe:recipe,baseStyle:recipe.monochrome ? "Monochrome":"Standard"))
        slots.sort{$0.slot<$1.slot}
    }

    func transport() throws -> DirectQ3Transport {
        guard let p=UInt16(cameraPort) else { throw Q3TransportError.invalidPacket("Invalid camera port.") }
        return DirectQ3Transport(host:cameraHost,port:p)
    }

    func probeQ3() {
        // IMPORTANT: do not mutate any @Published property from the button action or
        // from inside ImageCaptureCore's delegate/callback turn. macOS 26 can invoke
        // those callbacks while SwiftUI is still committing the control update, which
        // triggers "Publishing changes from within view updates" and can swallow the UI
        // refresh. Run the PTP transaction first, then publish exactly one final result
        // on a later main-run-loop turn.
        let usb = useUSB
        let host = cameraHost
        let portText = cameraPort

        Task { @MainActor in
            let finalMessage: String
            do {
                if usb {
                    finalMessage = try await USBQ3Bridge.shared.probe()
                } else {
                    guard let port = UInt16(portText) else {
                        throw Q3TransportError.invalidPacket("Invalid camera port.")
                    }
                    finalMessage = try await DirectQ3Transport(host: host, port: port).probe()
                }
            } catch {
                finalMessage = "USB test failed: \(error.localizedDescription)"
            }

            // Publish outside the ImageCaptureCore callback/view-update turn.
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.15) { [weak self] in
                self?.status = finalMessage
            }
        }
    }

    func readQ3Looks() {
        guard useUSB, !q3Busy else { return }
        q3Busy = true
        Task { @MainActor in
            let finalMessage: String
            do { finalMessage = try await USBQ3Bridge.shared.readLookPropertyList() }
            catch { finalMessage = "Look-list read failed: \(error.localizedDescription)" }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.15) { [weak self] in
                self?.q3Busy = false
                self?.status = finalMessage
            }
        }
    }


    func mvpInstallOfficialSilver() {
        guard useUSB, !q3Busy else { return }
        q3Busy = true
        Task { @MainActor in
            let message: String
            do {
                message = try await USBQ3Bridge.shared.installMVPOfficialSilver()
            } catch {
                message = "MVP Silver write failed: \(error.localizedDescription)"
            }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.15) { [weak self] in
                self?.q3Busy = false
                self?.status = message
            }
        }
    }

    func mvpInstallCustomIdentity() {
        guard useUSB, !q3Busy else { return }
        q3Busy = true
        Task { @MainActor in
            let message: String
            do {
                message = try await USBQ3Bridge.shared.installMVPCustomIdentity()
            } catch {
                message = "MVP custom-LUT write failed: \(error.localizedDescription)"
            }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.15) { [weak self] in
                self?.q3Busy = false
                self?.status = message
            }
        }
    }

    func installCurrent() {
        guard !q3Busy,let src=selectedLUT else{return}; q3Busy=true
        let recipe=self.recipe,name=outputName,id=max(1,lookID)
        status="Building \(name) and uploading to Q3…"
        Task {
            defer{q3Busy=false}
            do {
                let out=LUTTransforms.apply(recipe,to:src,outputSize:17,title:name)
                let base=recipe.monochrome ? "Monochrome":"Standard"
                let tmp=FileManager.default.temporaryDirectory.appendingPathComponent("IA-\(UUID().uuidString).CUBE")
                try CubeIO.write(out,url:tmp,lookID:id,baseStyle:base)
                defer{try? FileManager.default.removeItem(at:tmp)}
                let request = Q3InstallRequest(slot:1,lookID:UInt32(id),name:name,baseStyle:base,cubePath:tmp.path)
                if useUSB { try await USBQ3Bridge.shared.install(request) }
                else { try await transport().install(request) }
                status="Installed \(name) (Look ID \(id)) — Q3 returned 0x2001 OK."
            } catch { status=error.localizedDescription }
        }
    }

    func installSet() {
        guard !q3Busy,!slots.isEmpty else{return}; q3Busy=true
        let set=slots,baseID=max(1,lookID)
        status="Uploading \(set.count) Infinite Arch Looks…"
        Task {
            defer{q3Busy=false}
            do {
                var t: DirectQ3Transport? = nil
                if !useUSB { t = try transport() }
                for (index,slot) in set.sorted(by:{$0.slot<$1.slot}).enumerated() {
                    status="Uploading \(index+1)/\(set.count): \(slot.name)…"
                    let src=try CubeIO.read(url:URL(fileURLWithPath:slot.sourcePath))
                    let out=LUTTransforms.apply(slot.recipe,to:src,outputSize:17,title:slot.name)
                    let id=baseID+slot.slot-1
                    let tmp=FileManager.default.temporaryDirectory.appendingPathComponent("IA-\(UUID().uuidString).CUBE")
                    try CubeIO.write(out,url:tmp,lookID:id,baseStyle:slot.baseStyle)
                    defer{try? FileManager.default.removeItem(at:tmp)}
                    let request = Q3InstallRequest(slot:slot.slot,lookID:UInt32(id),name:slot.name,baseStyle:slot.baseStyle,cubePath:tmp.path)
                    if useUSB { try await USBQ3Bridge.shared.install(request) }
                    else { try await t!.install(request) }
                }
                status="Installed \(set.count) Looks. Q3 returned OK for every upload."
            } catch { status=error.localizedDescription }
        }
    }
}

struct BuilderView: View {
    @StateObject private var m = AppModel()

    var body: some View {
        HSplitView {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Button("LUT Pack…") { chooseFolder() }
                    Spacer()
                    Text("\(m.library.count)").foregroundStyle(.secondary)
                }
                TextField("Search LUTs", text: $m.search)
                List(m.filtered, id: \.path) { u in
                    Button(action: { m.load(u) }) {
                        HStack {
                            Text(u.deletingPathExtension().lastPathComponent)
                            Spacer()
                            if m.selectedSource?.path == u.path { Image(systemName: "checkmark") }
                        }
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(10)
            .frame(minWidth: 250)

            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    Text("Infinite Arch").font(.largeTitle).bold()

                    Picker("Recipe", selection: $m.recipe) {
                        ForEach(InfiniteArchRecipe.defaults) { r in
                            Text(r.name).tag(r)
                        }
                    }
                    .onChange(of: m.recipe) { newRecipe in
                        m.outputName = newRecipe.name
                    }

                    GroupBox("Look") {
                        VStack(spacing: 10) {
                            HStack {
                                Text("Name").frame(width: 90, alignment: .leading)
                                TextField("Name", text: $m.outputName)
                            }
                            SliderRow(title: "Strength", value: $m.recipe.strength, range: 0...1)
                            SliderRow(title: "Contrast", value: $m.recipe.contrast, range: -0.3...0.3)
                            SliderRow(title: "Saturation", value: $m.recipe.saturation, range: -0.4...0.4, disabled: m.recipe.monochrome)
                            SliderRow(title: "Warmth", value: $m.recipe.warmth, range: -0.3...0.3, disabled: m.recipe.monochrome)
                            SliderRow(title: "Highlights", value: $m.recipe.highlights, range: -0.4...0.4)
                            SliderRow(title: "Shadows", value: $m.recipe.shadows, range: -0.4...0.4)
                            HStack {
                                Text("Monochrome").frame(width: 90, alignment: .leading)
                                Toggle("", isOn: $m.recipe.monochrome)
                                Spacer()
                            }
                        }
                        .padding(8)
                    }

                    HStack {
                        Button("Add to 9-Slot Set") { m.addSlot() }
                            .disabled(m.selectedSource == nil || m.slots.count >= 9)
                        Button("Export Current CUBE") { exportCurrent() }
                            .disabled(m.selectedLUT == nil)
                        Button("Export 9-Slot Set") { exportSet() }
                            .disabled(m.slots.isEmpty)
                    }

                    GroupBox("Q3 Direct Install") {
                        VStack(alignment: .leading, spacing: 10) {
                            HStack {
                                Text("Transport").frame(width: 90, alignment: .leading)
                                Picker("", selection: $m.useUSB) {
                                    Text("USB-C / PTP").tag(true)
                                    Text("Wi-Fi / PTP-IP").tag(false)
                                }
                                .pickerStyle(.segmented)
                                .frame(maxWidth: 340)
                                Spacer()
                            }
                            if !m.useUSB {
                                HStack {
                                    Text("Camera").frame(width: 90, alignment: .leading)
                                    TextField("192.168.54.1", text: $m.cameraHost)
                                        .textFieldStyle(.roundedBorder)
                                    TextField("15740", text: $m.cameraPort)
                                        .frame(width: 78)
                                        .textFieldStyle(.roundedBorder)
                                }
                            } else {
                                HStack {
                                    Text("USB Q3").frame(width: 90, alignment: .leading)
                                    Text("Leica VID 0x1A98 · PID 0x2376 · ImageCaptureCore PTP")
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                    Spacer()
                                }
                            }
                            HStack {
                                Text("First Look ID").frame(width: 90, alignment: .leading)
                                TextField("1001", text: Binding<String>(
                                    get: { String(m.lookID) },
                                    set: { text in
                                        if let value = Int(text) { m.lookID = value }
                                    }
                                ))
                                .frame(width: 90)
                                .textFieldStyle(.roundedBorder)
                                Text("Set uses consecutive IDs.")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                                Spacer()
                            }
                            HStack {
                                Button(m.useUSB ? "Test USB PTP" : "Test Q3 Connection") {
                                    m.probeQ3()
                                }
                                Button("Read Q3 Look List") { m.readQ3Looks() }.disabled(m.q3Busy || !m.useUSB)
                                Button("Install Current to Q3") { m.installCurrent() }.disabled(m.q3Busy || m.selectedLUT == nil)
                                Button("Install Set to Q3") { m.installSet() }.disabled(m.q3Busy || m.slots.isEmpty)
                            }
                            if m.q3Busy { ProgressView().controlSize(.small) }
                        }
                        .padding(8)
                    }


                    GroupBox("MVP USB Write Test") {
                        VStack(alignment: .leading, spacing: 10) {
                            Text("Run Step 1 first. It installs an unused official Leica Silver Look (ID 24) using the exact FOTOS asset format. If that succeeds, Step 2 tests arbitrary LUT data using unused Leica Cine ID 27.")
                                .font(.caption)
                                .foregroundStyle(.secondary)

                            HStack {
                                Button("Step 1 — Install Official Silver") {
                                    m.mvpInstallOfficialSilver()
                                }
                                .disabled(m.q3Busy || !m.useUSB)

                                Button("Step 2 — Install Identity LUT Test") {
                                    m.mvpInstallCustomIdentity()
                                }
                                .disabled(m.q3Busy || !m.useUSB)

                                Spacer()
                            }
                        }
                        .padding(8)
                    }

                    GroupBox("Q3 Look Set") {
                        VStack(alignment: .leading, spacing: 6) {
                            if m.slots.isEmpty {
                                Text("No slots yet. Choose a LUT and recipe, then add it to the set.")
                                    .foregroundStyle(.secondary)
                            } else {
                                ForEach(m.slots) { slot in
                                    HStack {
                                        Text("\(slot.slot)").monospacedDigit().frame(width: 24)
                                        Text(slot.name).bold()
                                        Spacer()
                                        Text(slot.recipe.name).foregroundStyle(.secondary)
                                    }
                                }
                            }
                        }
                        .padding(8)
                    }

                    Text(m.status)
                        .font(.callout)
                        .foregroundStyle(.secondary)
                        .textSelection(.enabled)
                }
                .padding(22)
            }
            .frame(minWidth: 700)
        }
    }

    private func chooseFolder() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        if panel.runModal() == .OK, let url = panel.url {
            m.indexFolder(url)
        }
    }

    private func exportCurrent() {
        guard let source = m.selectedLUT else { return }
        let panel = NSSavePanel()
        panel.nameFieldStringValue = "\(m.outputName).CUBE"
        panel.allowedFileTypes = ["cube"]
        if panel.runModal() == .OK, let url = panel.url {
            do {
                let out = LUTTransforms.apply(m.recipe, to: source, outputSize: 17, title: m.outputName)
                try CubeIO.write(out, url: url, lookID: m.lookID, baseStyle: m.recipe.monochrome ? "Monochrome" : "Standard")
                m.status = "Exported \(url.lastPathComponent)."
            } catch {
                m.status = error.localizedDescription
            }
        }
    }

    private func exportSet() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.canCreateDirectories = true
        if panel.runModal() == .OK, let dir = panel.url {
            do {
                let manifest = LookSetManifest(name: "Infinite Arch Q3", slots: m.slots)
                let out = try LookSetExporter.export(
                    manifest: manifest,
                    sourceLoader: { path in try CubeIO.read(url: URL(fileURLWithPath: path)) },
                    to: dir
                )
                m.status = "Exported set to \(out.path)"
            } catch {
                m.status = error.localizedDescription
            }
        }
    }
}

struct SliderRow: View {
    let title: String
    @Binding var value: Double
    let range: ClosedRange<Double>
    var disabled = false

    var body: some View {
        HStack {
            Text(title).frame(width: 90, alignment: .leading)
            Slider(value: $value, in: range).disabled(disabled)
            Text(String(format: "%+.2f", value))
                .monospacedDigit()
                .frame(width: 54, alignment: .trailing)
        }
    }
}
