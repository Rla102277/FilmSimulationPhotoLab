import { useEffect, useMemo, useState } from "react";

type Look = {
  id: number;
  key: string;
  name: string;
  base_name: string;
  mono: boolean;
  cube_sha256: string;
  cube_bytes: number;
  icon_sha256: string;
};

type LookDetail = Look & {
  cube_summary: { title: string; size: number; rows: number; value_min: number; value_max: number; order: string };
  payload_summary: { bytes: number; sha256: string; field_count: number; fields: Array<{ property: string; datatype: string; name: string; value: unknown }> };
  provenance: { archive: string; immutable: boolean };
};

type InventoryItem = {
  relative_path: string;
  size: number;
  sha256: string;
  classification: string;
};

type SourceAsset = {
  id: string;
  filename: string;
  asset_type: string;
  size: number;
  sha256: string;
  provenance: string;
};

const api = async <T,>(path: string, options?: RequestInit): Promise<T> => {
  const response = await fetch(path, options);
  if (!response.ok) {
    const message = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(message.detail || response.statusText);
  }
  return response.json();
};

export function App() {
  const [looks, setLooks] = useState<Look[]>([]);
  const [selected, setSelected] = useState<number>(1004);
  const [detail, setDetail] = useState<LookDetail | null>(null);
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [view, setView] = useState<"library" | "sources" | "inventory" | "fuji">("library");
  const [error, setError] = useState("");
  const [originalUrl, setOriginalUrl] = useState("");
  const [renderedUrl, setRenderedUrl] = useState("");
  const [rendering, setRendering] = useState(false);
  const [recipeMessage, setRecipeMessage] = useState("");
  const [editorName, setEditorName] = useState("");
  const [editorId, setEditorId] = useState(1004);
  const [editorBase, setEditorBase] = useState(0);
  const [editorCube, setEditorCube] = useState<File | null>(null);
  const [editorIcon, setEditorIcon] = useState<File | null>(null);
  const [compileMessage, setCompileMessage] = useState("");
  const [description, setDescription] = useState("");
  const [provenance, setProvenance] = useState("Derived from authoritative v1.2 example");
  const [inspected, setInspected] = useState<Record<string, unknown> | null>(null);
  const [packIds, setPackIds] = useState<number[]>([]);
  const [sourceAssets, setSourceAssets] = useState<SourceAsset[]>([]);
  const [sourceMessage, setSourceMessage] = useState("");

  useEffect(() => {
    api<{ looks: Look[] }>("/api/library")
      .then((data) => setLooks(data.looks))
      .catch((reason) => setError(String(reason)));
  }, []);

  useEffect(() => {
    if (view === "library") {
      api<LookDetail>(`/api/looks/${selected}`).then((data) => {
        setDetail(data);
        setEditorName(data.name);
        setEditorId(data.id);
        setEditorBase(data.mono ? 1 : 0);
        setEditorCube(null);
        setEditorIcon(null);
        setCompileMessage("");
      }).catch((reason) => setError(String(reason)));
    }
  }, [selected, view]);

  useEffect(() => {
    if (view === "inventory" && inventory.length === 0) {
      api<{ items: InventoryItem[] }>("/api/inventory")
        .then((data) => setInventory(data.items))
        .catch((reason) => setError(String(reason)));
    }
  }, [view, inventory.length]);

  useEffect(() => {
    if (view === "sources") {
      api<SourceAsset[]>("/api/assets").then(setSourceAssets).catch((reason) => setError(String(reason)));
    }
  }, [view]);

  const selectedLook = useMemo(() => looks.find((look) => look.id === selected), [looks, selected]);

  useEffect(() => {
    if (looks.length && packIds.length === 0) setPackIds(looks.map((look) => look.id));
  }, [looks, packIds.length]);

  function startNewLook() {
    const used = new Set(looks.map((look) => look.id));
    let suggested = 1100;
    while (used.has(suggested)) suggested += 1;
    setEditorName("Untitled Leica Look");
    setEditorId(suggested);
    setEditorBase(0);
    setEditorCube(null);
    setEditorIcon(null);
    setDescription("");
    setProvenance(`Started from ${selectedLook?.name || "a v1.2 regression example"}`);
    setCompileMessage("New Look draft · add your own CUBE or use the selected example as a starting transform.");
  }

  async function renderImage(file: File) {
    setRendering(true);
    setError("");
    if (originalUrl) URL.revokeObjectURL(originalUrl);
    if (renderedUrl) URL.revokeObjectURL(renderedUrl);
    setOriginalUrl(URL.createObjectURL(file));
    const form = new FormData();
    form.append("image", file);
    try {
      const response = await fetch(`/api/looks/${selected}/render`, { method: "POST", body: form });
      if (!response.ok) throw new Error((await response.json()).detail);
      setRenderedUrl(URL.createObjectURL(await response.blob()));
    } catch (reason) {
      setError(String(reason));
    } finally {
      setRendering(false);
    }
  }

  async function saveRecipe(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const settings = Object.fromEntries(
      ["film_simulation", "dynamic_range", "highlight", "shadow", "color", "white_balance_mode"]
        .map((key) => [key, String(form.get(key) || "").trim()])
        .filter(([, value]) => value),
    );
    try {
      const result = await api<{ id: string; warning: string }>("/api/fuji/recipes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: form.get("name"),
          camera_profile_id: form.get("camera"),
          look_id: selected,
          settings,
          provenance: form.get("provenance"),
        }),
      });
      setRecipeMessage(`Saved experimental recipe ${result.id.slice(0, 8)}. ${result.warning}`);
      event.currentTarget.reset();
    } catch (reason) {
      setRecipeMessage(String(reason));
    }
  }

  function saveBlob(blob: Blob, filename: string) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function compileAndDownload() {
    setCompileMessage("Compiling, parsing, and verifying…");
    const form = new FormData();
    form.append("look_id", String(editorId));
    form.append("name", editorName);
    form.append("base", String(editorBase));
    form.append("d864", "2");
    form.append("source_look_id", String(selected));
    if (editorCube) form.append("cube", editorCube);
    if (editorIcon) form.append("icon", editorIcon);
    try {
      const response = await fetch("/api/leica/compile", { method: "POST", body: form });
      if (!response.ok) throw new Error((await response.json()).detail);
      saveBlob(await response.blob(), `${editorName.toLowerCase().replace(/[^a-z0-9]+/g, "-")}.leica-payload.bin`);
      setCompileMessage(`VALID · ${response.headers.get("X-Payload-SHA256")?.slice(0, 16)}… · downloaded`);
    } catch (reason) {
      setCompileMessage(String(reason));
    }
  }

  async function buildLookPackage() {
    setCompileMessage("Building verified payload, injector, documentation, and checksums…");
    const form = new FormData();
    form.append("look_id", String(editorId));
    form.append("name", editorName);
    form.append("base", String(editorBase));
    form.append("source_look_id", String(selected));
    form.append("description", description);
    form.append("provenance", provenance);
    if (editorCube) form.append("cube", editorCube);
    if (editorIcon) form.append("icon", editorIcon);
    try {
      const response = await fetch("/api/leica/package", { method: "POST", body: form });
      if (!response.ok) throw new Error((await response.json()).detail);
      saveBlob(await response.blob(), `${editorName.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-leica-look-package.zip`);
      setCompileMessage(`READY · round-trip PASS · package ${response.headers.get("X-Package-SHA256")?.slice(0, 16)}…`);
    } catch (reason) {
      setCompileMessage(String(reason));
    }
  }

  async function inspectPayload(file: File) {
    const form = new FormData();
    form.append("payload", file);
    try {
      setInspected(await api<Record<string, unknown>>("/api/leica/inspect", { method: "POST", body: form }));
    } catch (reason) {
      setInspected({ validation: "INVALID", error: String(reason) });
    }
  }

  async function downloadPack() {
    try {
      const response = await fetch("/api/leica/packs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ look_ids: packIds }),
      });
      if (!response.ok) throw new Error((await response.json()).detail);
      saveBlob(await response.blob(), "infinite-arch-leica-look-pack.zip");
    } catch (reason) {
      setError(String(reason));
    }
  }

  async function uploadSource(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const values = new FormData(formElement);
    const file = values.get("asset");
    const sourceProvenance = String(values.get("provenance") || "");
    if (!(file instanceof File)) return;
    const body = new FormData();
    body.append("asset", file);
    setSourceMessage("Inspecting and preserving immutable source…");
    try {
      const result = await api<{ asset_type: string; sha256: string }>(`/api/assets?provenance=${encodeURIComponent(sourceProvenance)}`, { method: "POST", body });
      setSourceMessage(`${result.asset_type.toUpperCase()} preserved · ${result.sha256.slice(0, 16)}…`);
      formElement.reset();
      setSourceAssets(await api<SourceAsset[]>("/api/assets"));
    } catch (reason) {
      setSourceMessage(String(reason));
    }
  }

  return (
    <div className="app-shell">
      <aside>
        <a className="brand" href="/">
          <span>IA</span>
          <strong>Infinite Arch<br />Photo Lab</strong>
        </a>
        <nav aria-label="Primary">
          {[
            ["library", "Leica library"],
            ["sources", "Sources"],
            ["inventory", "Provenance"],
            ["fuji", "Fuji recipes"],
          ].map(([key, label]) => (
            <button className={view === key ? "active" : ""} onClick={() => setView(key as typeof view)} key={key}>
              {label}
            </button>
          ))}
        </nav>
        <div className="aside-foot">
          <span className="online-dot" /> Archive verified
          <a href="/look-building">How a Look is built</a>
          <a href="/docs">API documentation</a>
        </div>
      </aside>

      <main>
        {error && <div className="error" role="alert">{error}</div>}
        {view === "library" && (
          <>
            <header>
              <div>
                <p className="eyebrow">General-purpose creation tool</p>
                <h1>Leica Look Factory</h1>
              </div>
              <button className="primary" onClick={startNewLook}>New Look</button>
            </header>
            <p className="intro">Create an original Leica Look from arbitrary source material. The nine v1.2 Looks below are known-good examples and regression fixtures.</p>
            <section className="look-strip" aria-label="Looks">
              {looks.map((look) => (
                <button className={selected === look.id ? "selected" : ""} onClick={() => setSelected(look.id)} key={look.id}>
                  <img src={`/api/looks/${look.id}/icon`} alt="" />
                  <span>{look.name.replace("IA ", "")}</span>
                  <small>{look.id} · {look.base_name}</small>
                </button>
              ))}
            </section>
            {detail && selectedLook && (
              <section className="detail-grid">
                <article className="hero-panel">
                  <p className="eyebrow">Leica Look Lab</p>
                  <h2>{detail.name}</h2>
                  <p>Edit a controlled copy of the authoritative record. The v1.2 archive remains unchanged.</p>
                  <div className="compact-form">
                    <label>Name<input value={editorName} onChange={(event) => setEditorName(event.target.value)} /></label>
                    <label>Custom ID<input type="number" min="1000" value={editorId} onChange={(event) => setEditorId(Number(event.target.value))} /></label>
                    <label>Base<select value={editorBase} onChange={(event) => setEditorBase(Number(event.target.value))}><option value={0}>Standard</option><option value={1}>Monochrome</option></select></label>
                    <label>Primary LUT<input type="file" accept=".cube" onChange={(event) => setEditorCube(event.target.files?.[0] || null)} /></label>
                    <label>Icon BMP<input type="file" accept=".bmp" onChange={(event) => setEditorIcon(event.target.files?.[0] || null)} /></label>
                    <label className="wide">Visual intent<input value={description} placeholder="Warm documentary color with restrained highlights" onChange={(event) => setDescription(event.target.value)} /></label>
                    <label className="wide">Source provenance<input value={provenance} onChange={(event) => setProvenance(event.target.value)} /></label>
                  </div>
                  <div className="button-row">
                    <button className="primary" onClick={buildLookPackage}>Build Look package</button>
                    <button className="secondary" onClick={compileAndDownload}>Payload only</button>
                  </div>
                  {compileMessage && <p className="message">{compileMessage}</p>}
                </article>
                <article className="preview-panel">
                  <div className="preview-head">
                    <div><p className="eyebrow">Software preview</p><h3>Test the authoritative CUBE</h3></div>
                    <label className="upload-button">Choose image<input type="file" accept="image/jpeg,image/png,image/webp" onChange={(e) => e.target.files?.[0] && renderImage(e.target.files[0])} /></label>
                  </div>
                  {rendering && <div className="empty-preview">Rendering {detail.name}…</div>}
                  {!rendering && renderedUrl && (
                    <div className="comparison">
                      <figure><img src={originalUrl} alt="Original upload" /><figcaption>Original</figcaption></figure>
                      <figure><img src={renderedUrl} alt={`Rendered with ${detail.name}`} /><figcaption>{detail.name}</figcaption></figure>
                    </div>
                  )}
                  {!rendering && !renderedUrl && <div className="empty-preview">Upload a JPEG, PNG, or WebP for a non-destructive preview.</div>}
                </article>
              </section>
            )}
            {detail && (
              <section className="lab-tools">
                <article className="payload-card">
                  <div><p className="eyebrow">Serialized record</p><h2>Leica payload</h2></div>
                  <div className="field-list">
                    {detail.payload_summary.fields.map((field) => (
                      <div key={field.property}>
                        <code>{field.property}</code>
                        <span>{field.name === "type" ? "D864" : field.name}</span>
                        <strong>{typeof field.value === "object" ? `${(field.value as { bytes: number }).bytes.toLocaleString()} bytes` : String(field.value)}</strong>
                        <small>{field.datatype}</small>
                        <b>VALID</b>
                      </div>
                    ))}
                  </div>
                  <p className="validation-line">Payload VALID · {detail.payload_summary.bytes.toLocaleString()} bytes · compile → parse → verify enforced</p>
                </article>
                <article className="inspector-card">
                  <p className="eyebrow">Existing payload</p>
                  <h2>Look inspector</h2>
                  <label className="upload-button">Inspect Leica payload<input type="file" accept=".bin,application/octet-stream" onChange={(event) => event.target.files?.[0] && inspectPayload(event.target.files[0])} /></label>
                  {inspected && <pre>{JSON.stringify(inspected, null, 2)}</pre>}
                </article>
                <article className="pack-card">
                  <p className="eyebrow">Multi-Look export</p>
                  <h2>Pack builder</h2>
                  <div className="pack-options">{looks.map((look) => (
                    <label key={look.id}><input type="checkbox" checked={packIds.includes(look.id)} onChange={() => setPackIds((current) => current.includes(look.id) ? current.filter((id) => id !== look.id) : [...current, look.id])} />{look.name}</label>
                  ))}</div>
                  <button className="primary" disabled={!packIds.length} onClick={downloadPack}>Build and download pack</button>
                  <p className="muted">ZIP includes verified payload binaries, CUBEs, icons, and a checksum manifest. It does not claim an undocumented SD-card import container.</p>
                </article>
              </section>
            )}
          </>
        )}

        {view === "inventory" && (
          <>
            <header><div><p className="eyebrow">Immutable source record</p><h1>Provenance</h1></div></header>
            <p className="intro">Every member is read from the authoritative ZIP and classified without modifying the original.</p>
            <div className="table-wrap"><table><thead><tr><th>File</th><th>Classification</th><th>Bytes</th><th>SHA-256</th></tr></thead>
              <tbody>{inventory.map((item) => <tr key={item.relative_path}><td>{item.relative_path}</td><td>{item.classification.replaceAll("_", " ")}</td><td>{item.size.toLocaleString()}</td><td><code>{item.sha256.slice(0, 16)}…</code></td></tr>)}</tbody>
            </table></div>
          </>
        )}

        {view === "sources" && (
          <>
            <header><div><p className="eyebrow">General-purpose factory</p><h1>Source Library</h1></div></header>
            <p className="intro">Import arbitrary CUBE, DCP, LRTemplate, XMP, Hald, image, DNG, or RAF material. Originals are preserved by checksum and never replaced by generated derivatives.</p>
            <form className="source-upload" onSubmit={uploadSource}>
              <label>Source file<input name="asset" type="file" required accept=".cube,.dcp,.lrtemplate,.xmp,.jpg,.jpeg,.png,.tif,.tiff,.dng,.raf" /></label>
              <label>Provenance<input name="provenance" required minLength={3} placeholder="Source, author, license, and intended use" /></label>
              <button className="primary" type="submit">Add source</button>
            </form>
            {sourceMessage && <p className="message">{sourceMessage}</p>}
            <div className="source-grid">{sourceAssets.map((asset) => (
              <article key={asset.id}>
                <span>{asset.asset_type.replaceAll("_", " ")}</span>
                <h3>{asset.filename}</h3>
                <p>{asset.provenance}</p>
                <code>{asset.sha256.slice(0, 20)}…</code>
                <a href={`/api/assets/${asset.id}/download`}>Download original</a>
              </article>
            ))}</div>
          </>
        )}

        {view === "fuji" && (
          <>
            <header><div><p className="eyebrow">Phase A · capability-aware</p><h1>Fuji Recipe Lab</h1></div></header>
            <p className="intro">Store experimental target-specific recipes without claiming unverified camera support. X-E5 and GFX 50R remain separate capability profiles.</p>
            <form className="editor-form" onSubmit={saveRecipe}>
              <label>Name<input name="name" required placeholder="Presence · X-E5 experiment 01" /></label>
              <label>Camera<select name="camera"><option value="FUJI_X_E5">Fujifilm X-E5</option><option value="FUJI_GFX50R">Fujifilm GFX 50R</option></select></label>
              <label>Film simulation<input name="film_simulation" placeholder="Record observed value only" /></label>
              <label>Dynamic range<input name="dynamic_range" /></label>
              <label>Highlight<input name="highlight" /></label>
              <label>Shadow<input name="shadow" /></label>
              <label>Color<input name="color" /></label>
              <label>White balance mode<input name="white_balance_mode" /></label>
              <label className="wide">Provenance<textarea name="provenance" required placeholder="Who supplied or measured these settings, on which body/firmware, and how they were verified." /></label>
              <button className="primary" type="submit">Save experimental recipe</button>
            </form>
            {recipeMessage && <p className="message">{recipeMessage}</p>}
          </>
        )}

      </main>
    </div>
  );
}