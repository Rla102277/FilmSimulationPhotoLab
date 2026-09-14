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
  payload_summary: { bytes: number; sha256: string; field_count: number; fields: Array<{ property: string; name: string; value: unknown }> };
  provenance: { archive: string; immutable: boolean };
};

type InventoryItem = {
  relative_path: string;
  size: number;
  sha256: string;
  classification: string;
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
  const [view, setView] = useState<"library" | "inventory" | "fuji" | "bridge">("library");
  const [error, setError] = useState("");
  const [originalUrl, setOriginalUrl] = useState("");
  const [renderedUrl, setRenderedUrl] = useState("");
  const [rendering, setRendering] = useState(false);
  const [recipeMessage, setRecipeMessage] = useState("");
  const [jobMessage, setJobMessage] = useState("");

  useEffect(() => {
    api<{ looks: Look[] }>("/api/library")
      .then((data) => setLooks(data.looks))
      .catch((reason) => setError(String(reason)));
  }, []);

  useEffect(() => {
    if (view === "library") {
      api<LookDetail>(`/api/looks/${selected}`).then(setDetail).catch((reason) => setError(String(reason)));
    }
  }, [selected, view]);

  useEffect(() => {
    if (view === "inventory" && inventory.length === 0) {
      api<{ items: InventoryItem[] }>("/api/inventory")
        .then((data) => setInventory(data.items))
        .catch((reason) => setError(String(reason)));
    }
  }, [view, inventory.length]);

  const selectedLook = useMemo(() => looks.find((look) => look.id === selected), [looks, selected]);

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

  async function queueReadJob() {
    try {
      const job = await api<{ id: string; status: string }>("/api/bridge/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_type: "LEICA_READ_LOOKS", payload: { target_camera: "LEICA_Q3_FAMILY" } }),
      });
      setJobMessage(`Queued read-only job ${job.id.slice(0, 8)} · ${job.status}`);
    } catch (reason) {
      setJobMessage(String(reason));
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
            ["inventory", "Provenance"],
            ["fuji", "Fuji recipes"],
            ["bridge", "Camera bridge"],
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
                <p className="eyebrow">Authoritative release · Leica v1.2</p>
                <h1>The Look Library</h1>
              </div>
              <div className="release-stamp">9 Looks<br /><span>IDs 1001–1009</span></div>
            </header>
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
                  <p className="eyebrow">Camera implementation</p>
                  <h2>{detail.name}</h2>
                  <p>A verified Leica Q3-family implementation read directly from the immutable v1.2 archive.</p>
                  <dl>
                    <div><dt>Base</dt><dd>{detail.base_name}</dd></div>
                    <div><dt>LUT</dt><dd>{detail.cube_summary.size}³ · {detail.cube_summary.rows.toLocaleString()} rows</dd></div>
                    <div><dt>Order</dt><dd>{detail.cube_summary.order}</dd></div>
                    <div><dt>Payload</dt><dd>{detail.payload_summary.bytes.toLocaleString()} bytes</dd></div>
                  </dl>
                  <details>
                    <summary>Checksums and payload fields</summary>
                    <code>{detail.cube_sha256}</code>
                    <ul>{detail.payload_summary.fields.map((field) => <li key={field.property}>{field.property} · {field.name}</li>)}</ul>
                  </details>
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

        {view === "bridge" && (
          <>
            <header><div><p className="eyebrow">Outbound local connection only</p><h1>IA Camera Bridge</h1></div></header>
            <div className="bridge-grid">
              <article><h2>Safe boundary</h2><p>The Replit service never connects to a camera LAN address. A paired bridge on the local Mac claims validated jobs over an outbound authenticated connection.</p></article>
              <article><h2>Read before write</h2><p>Camera information and the current Look table must be readable before any Leica installation. An ambiguous write is never retried.</p></article>
              <article><h2>Verify after write</h2><p>A successful write response is not enough. The bridge must re-read the camera Look table before reporting success.</p></article>
            </div>
            <button className="primary" onClick={queueReadJob}>Queue read-only Leica Look-table job</button>
            {jobMessage && <p className="message">{jobMessage}</p>}
            <p className="muted">Bridge registration and authenticated claim/heartbeat endpoints are available in the API documentation. Hardware execution requires the local companion process and a camera.</p>
          </>
        )}
      </main>
    </div>
  );
}