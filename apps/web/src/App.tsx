import { useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent } from "react";
import { useClerk, useUser } from "@clerk/react";

type View = "studio" | "mylooks" | "library" | "sources" | "inventory" | "fuji";
type Component = { blendable?: boolean; reason?: string; id?: string; component_id?: string; type?: string; name?: string; details?: Record<string, unknown>; source?: string; source_id?: string };
type Source = { id: string; filename?: string; display_name?: string; name?: string; type?: string; asset_type?: string; sha256?: string; provenance?: string; components?: Component[] };
type CatalogProfile = { catalog_id: string; display_name: string; brand: string; stock: string; modification: string; asset_type: "dcp" | "cube"; size: number };
type Layer = { id: string; name: string; type: string; enabled: boolean; strength: number; role?: "base" | "creative"; source?: string; source_id?: string; component_id?: string; params?: Record<string, number> };
type Graph = { name: string; version: string; look_id: number; base: string; layers: Layer[]; controls: Record<string, number>; solo?: string | null };
type SavedGraph = { id: string; name: string; graph: Graph; updated_at: string };

const errorMessage = (detail: unknown): string => {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map(errorMessage).join("; ");
  if (detail && typeof detail === "object") {
    const value = detail as Record<string, unknown>;
    return [value.message, value.error, value.reason, value.errors, value.unsupported].filter(Boolean).map(errorMessage).filter(Boolean).join("; ") || JSON.stringify(detail);
  }
  return String(detail || "Request failed");
};
const api = async <T,>(path: string, options?: RequestInit): Promise<T> => {
  const res = await fetch(path, options);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(errorMessage(body.detail || res.statusText));
  }
  return res.json();
};
const id = () => Math.random().toString(36).slice(2, 9);
const initialLayers: Layer[] = [
  { id: id(), name: "Input Normalization", type: "normalization", enabled: true, strength: 100 },
  { id: id(), name: "Output Normalize", type: "output", enabled: true, strength: 100 },
];
const defaultControls: Record<string, number> = {"exposure": 0, "contrast": 0, "highlights": 0, "shadows": 0, "whites": 0, "blacks": 0, "temperature": 0, "tint": 0, "saturation": 0, "vibrance": 0, "shadowHue": 0, "shadowSat": 0, "shadowLum": 0, "midHue": 0, "midSat": 0, "midLum": 0, "highlightHue": 0, "highlightSat": 0, "highlightLum": 0, "balance": 0, "toe": 0, "shoulder": 0, "midContrast": 0, "blackLift": 0, "rolloff": 0, "density": 0, "monoMix": 0, "yellowFilter": 0, "orangeFilter": 0, "redFilter": 0, "greenFilter": 0};
const toApiGraph = (graph: Graph): Graph => ({ ...graph, solo: graph.solo || null });
const withBaseLayers = (graph: Graph, baseLayers: Layer[], name: string): Graph => {
  const retained = graph.layers.filter((layer) => layer.role !== "base");
  const outputIndex = retained.findIndex((layer) => layer.type === "output");
  const insertion = outputIndex < 0 ? retained.length : outputIndex;
  return { ...graph, name, layers: [...retained.slice(0, insertion), ...baseLayers, ...retained.slice(insertion)] };
};

export function App() {
  const { signOut } = useClerk();
  const { user } = useUser();
  const [view, setView] = useState<View>("studio");
  const [graph, setGraph] = useState<Graph>({ name: "Untitled Leica Look", version: "v1.0", look_id: 1142, base: "Standard", layers: initialLayers, controls: defaultControls, solo: null });
  const [history, setHistory] = useState<Graph[]>([]);
  const [future, setFuture] = useState<Graph[]>([]);
  const [snapshots, setSnapshots] = useState<{ name: string; graph: Graph }[]>([]);
  const [selectedLayer, setSelectedLayer] = useState<string>(initialLayers[0].id);
  const [solo, setSolo] = useState<string | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [profiles, setProfiles] = useState<CatalogProfile[]>([]);
  const [sourceRevision, setSourceRevision] = useState(0);
  const [sourceSearch, setSourceSearch] = useState("");
  const [sourceType, setSourceType] = useState("");
  const [openSource, setOpenSource] = useState<string | null>(null);
  const [sourceError, setSourceError] = useState("");
  const [image, setImage] = useState<File | null>(null);
  const [originalUrl, setOriginalUrl] = useState("");
  const [previewUrl, setPreviewUrl] = useState("");
  const [previewMode, setPreviewMode] = useState<"wipe" | "side">("wipe");
  const [wipe, setWipe] = useState(50);
  const [rendering, setRendering] = useState(false);
  const [zoom, setZoom] = useState<"fit" | "100">("fit");
  const [message, setMessage] = useState("");
  const [snapshotName, setSnapshotName] = useState("");
  const [status, setStatus] = useState<Record<string, unknown> | null>(null);
  const [workspaces, setWorkspaces] = useState<SavedGraph[]>([]);
  const [savedLooks, setSavedLooks] = useState<SavedGraph[]>([]);
  const [selectedLooks, setSelectedLooks] = useState<string[]>([]);
  const [selectedCatalogId, setSelectedCatalogId] = useState<string | null>(null);
  const previewTimer = useRef<number | undefined>(undefined);
  const statusTimer = useRef<number | undefined>(undefined);
  const sliderHistoryTimer = useRef<number | undefined>(undefined);
  const sliderStart = useRef<Graph | null>(null);
  const previewRequest = useRef<AbortController | null>(null);
  const statusRequest = useRef<AbortController | null>(null);
  const profileRequestSequence = useRef(0);
  const profileCache = useRef(new Map<string, Source>());

  useEffect(() => {
    if (view !== "studio" && view !== "sources") return;
    const query = new URLSearchParams({ search: sourceSearch, type: sourceType });
    api<Source[] | { sources: Source[] }>(`/api/studio/sources?${query}`).then((data) => setSources(Array.isArray(data) ? data : data.sources)).catch((e) => setSourceError(String(e)));
    api<{ profiles: CatalogProfile[] }>(`/api/studio/profile-catalog?${query}`).then((data) => setProfiles(data.profiles)).catch((e) => setSourceError(String(e)));
  }, [view, sourceSearch, sourceType, sourceRevision]);
  useEffect(() => {
    if (view !== "mylooks") return;
    Promise.all([api<SavedGraph[]>("/api/studio/workspaces"), api<SavedGraph[]>("/api/studio/looks")])
      .then(([nextWorkspaces, nextLooks]) => { setWorkspaces(nextWorkspaces); setSavedLooks(nextLooks); })
      .catch((error) => setMessage(String(error)));
  }, [view]);
  useEffect(() => {
    setStatus(null);
    window.clearTimeout(statusTimer.current);
    statusRequest.current?.abort();
    statusTimer.current = window.setTimeout(() => {
      const controller = new AbortController();
      statusRequest.current = controller;
      api<Record<string, unknown>>("/api/studio/graph/status", { method: "POST", signal: controller.signal, headers: { "Content-Type": "application/json" }, body: JSON.stringify(toApiGraph({ ...graph, solo })) }).then((next) => { if (!controller.signal.aborted) setStatus(next); }).catch((error) => { if (error.name !== "AbortError") setStatus(null); });
    }, 350);
    return () => { window.clearTimeout(statusTimer.current); statusRequest.current?.abort(); };
  }, [graph, solo]);
  useEffect(() => {
    setPreviewUrl((old) => { if (old) URL.revokeObjectURL(old); return ""; });
    if (!image) return;
    window.clearTimeout(previewTimer.current);
    previewRequest.current?.abort();
    previewTimer.current = window.setTimeout(async () => {
      const controller = new AbortController();
      previewRequest.current = controller;
      setRendering(true);
      const form = new FormData(); form.append("image", image); form.append("graph", JSON.stringify(toApiGraph({ ...graph, solo })));
      try { const res = await fetch("/api/studio/graph/preview", { method: "POST", body: form, signal: controller.signal }); if (!res.ok) { const body = await res.json().catch(() => ({})); throw new Error(errorMessage(body.detail || res.statusText || "Preview renderer unavailable")); } const blob = await res.blob(); if (controller.signal.aborted) return; const nextUrl = URL.createObjectURL(blob); setPreviewUrl((old) => { if (old) URL.revokeObjectURL(old); return nextUrl; }); } catch (e) { if ((e as Error).name !== "AbortError") setMessage(String(e)); } finally { if (previewRequest.current === controller) setRendering(false); }
    }, 120);
    return () => { window.clearTimeout(previewTimer.current); previewRequest.current?.abort(); };
  }, [graph, image, solo]);

  const displayedLayers = useMemo(() => solo ? graph.layers.map((l) => ({ ...l, enabled: l.id === solo || l.type === "normalization" || l.type === "output" })) : graph.layers, [graph.layers, solo]);
  function mutate(next: Graph) { setHistory((h) => [...h.slice(-29), graph]); setFuture([]); setGraph(next); setSolo(next.solo || null); }
  function setSoloLayer(layerId: string | null) { setSolo(layerId); setGraph((current) => ({ ...current, solo: layerId })); }
  function updateLayer(layerId: string, patch: Partial<Layer>) { mutate({ ...graph, layers: graph.layers.map((l) => l.id === layerId ? { ...l, ...patch } : l) }); }
  function beginSliderChange() {
    if (!sliderStart.current) sliderStart.current = graph;
    window.clearTimeout(sliderHistoryTimer.current);
    sliderHistoryTimer.current = window.setTimeout(() => {
      const start = sliderStart.current;
      if (start) setHistory((items) => [...items.slice(-29), start]);
      sliderStart.current = null;
      setFuture([]);
    }, 300);
  }
  function updateControl(key: string, value: number) { beginSliderChange(); setGraph((current) => ({ ...current, controls: { ...current.controls, [key]: value } })); }
  function updateLayerStrength(layerId: string, strength: number) { beginSliderChange(); setGraph((current) => ({ ...current, layers: current.layers.map((layer) => layer.id === layerId ? { ...layer, strength } : layer) })); }
  function moveLayer(layerId: string, delta: number) { const at = graph.layers.findIndex((l) => l.id === layerId); const to = at + delta; if (at < 0 || to < 0 || to >= graph.layers.length) return; const layers = [...graph.layers]; [layers[at], layers[to]] = [layers[to], layers[at]]; mutate({ ...graph, layers }); }
  function undo() { const previous = history.at(-1); if (!previous) return; setFuture((f) => [graph, ...f]); setHistory((h) => h.slice(0, -1)); setGraph(previous); setSolo(previous.solo || null); }
  function redo() { const next = future[0]; if (!next) return; setHistory((h) => [...h, graph]); setFuture((f) => f.slice(1)); setGraph(next); setSolo(next.solo || null); }
  function addComponent(component: Component, source?: Source) {
    if (component.blendable === false) { setMessage(component.reason || "This component is available for inspection only."); return; }
    const name = component.name || component.component_id || component.id || component.type || "Source component";
    const layer: Layer = { id: id(), name, type: (component.type || "component").toLowerCase(), role: "creative", source: source?.filename || source?.name, source_id: component.source_id || source?.id, component_id: component.component_id || component.id, enabled: true, strength: 100 };
    mutate({ ...graph, layers: [...graph.layers.slice(0, -1), layer, graph.layers.at(-1)!] }); setSelectedLayer(layer.id); setMessage(`${name} added to the live graph`);
  }
  async function useCatalogProfile(profile: CatalogProfile) {
    const sequence = ++profileRequestSequence.current;
    setSelectedCatalogId(profile.catalog_id);
    setMessage(`Loading ${profile.display_name}…`);
    try {
      const source = profileCache.current.get(profile.catalog_id)
        || await api<Source>(`/api/studio/profile-catalog/${profile.catalog_id}/import`, { method: "POST" });
      if (sequence !== profileRequestSequence.current) return;
      profileCache.current.set(profile.catalog_id, source);
      const components = source.components || [];
      const selected = profile.asset_type === "cube"
        ? components.filter((component) => component.type === "cube_lut").slice(0, 1)
        : components.filter((component) => ["ProfileToneCurve"].includes(component.id || component.component_id || ""));
      const usable = selected.length ? selected : components.filter((component) => component.blendable !== false && ["cube_lut", "tone_curve"].includes(component.type || ""));
      if (!usable.length) throw new Error(`${profile.display_name} has no safely editable DCP components`);
      const layers = usable.map((component) => ({
        id: id(),
        name: `${profile.display_name} · ${component.id || component.type}`,
        type: (component.type || "component").toLowerCase(),
        source: source.filename,
        source_id: source.id,
        component_id: component.id || component.component_id,
        enabled: true,
        strength: 100,
        role: "base" as const,
      }));
      setHistory((items) => [...items.slice(-29), graph]);
      setFuture([]);
      setGraph((current) => withBaseLayers(current, layers, profile.display_name));
      setSelectedLayer(layers[0].id);
      setSources((all) => all.some((item) => item.id === source.id) ? all : [source, ...all]);
      setMessage(`${profile.display_name} loaded${profile.asset_type === "dcp" ? " as a creative tone curve. Camera calibration matrices and unevaluated tables remain inspection-only." : " as the editable base"}`);
    } catch (e) {
      setMessage(String(e));
    }
  }
  async function uploadSources(event: ChangeEvent<HTMLInputElement>) {
    const files = event.target.files; if (!files?.length) return;
    const form = new FormData(); Array.from(files).forEach((f) => form.append("files", f)); form.append("provenance", "Uploaded to Film Look Studio source library");
    setMessage(`Ingesting ${files.length} source${files.length > 1 ? "s" : ""}…`);
    try { await api("/api/studio/sources/bulk", { method: "POST", body: form }); setMessage("Sources catalogued; duplicates are preserved by SHA-256 rules."); setSourceRevision((value) => value + 1); event.target.value = ""; } catch (e) { setMessage(String(e)); }
  }
  async function buildCube() { try { const res = await fetch("/api/studio/graph/cube", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(toApiGraph({ ...graph, solo })) }); if (!res.ok) { const body = await res.json().catch(() => ({})); throw new Error(errorMessage(body.detail || res.statusText || "CUBE export failed")); } download(await res.blob(), `${graph.name}.cube`); } catch (e) { setMessage(String(e)); } }
  async function buildPackage() { try { const form = new FormData(); form.append("graph", JSON.stringify(toApiGraph({ ...graph, solo }))); form.append("name", graph.name); form.append("look_id", String(graph.look_id)); form.append("base", graph.base); form.append("description", "Non-destructive creative graph from Film Look Studio"); const res = await fetch("/api/studio/graph/package", { method: "POST", body: form }); if (!res.ok) { const body = await res.json().catch(() => ({})); throw new Error(errorMessage(body.detail || res.statusText || "Package build failed")); } download(await res.blob(), `${graph.name.replace(/\s+/g, "-").toLowerCase()}-package.zip`); setMessage("Package ready: payload, injector, documentation and checksums."); } catch (e) { setMessage(String(e)); } }
  async function saveWorkspace() { try { await api("/api/studio/workspaces", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: graph.name, graph }) }); setMessage(`${graph.name} workspace saved privately`); } catch (e) { setMessage(String(e)); } }
  async function saveLook() { try { await api("/api/studio/looks", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: graph.name, graph }) }); setMessage(`${graph.name} added to My Looks`); } catch (e) { setMessage(String(e)); } }
  async function reviewGraph() { try { setMessage("Running deterministic 17³ validation and AI review…"); const result = await api<{ valid: boolean; provider: string; findings: string[] }>("/api/studio/graph/review", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(toApiGraph({ ...graph, solo })) }); setMessage(`${result.valid ? "Verified" : "Review failed"} · ${result.provider}: ${result.findings.join(" ")}`); } catch (e) { setMessage(String(e)); } }
  async function downloadSelectedLooks() { try { const res = await fetch("/api/studio/looks/package", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ look_ids: selectedLooks }) }); if (!res.ok) { const body = await res.json().catch(() => ({})); throw new Error(errorMessage(body.detail || res.statusText)); } download(await res.blob(), "film-look-studio-selection.zip"); } catch (e) { setMessage(String(e)); } }
  function download(blob: Blob, name: string) { const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = name; a.click(); }
  function chooseImage(event: ChangeEvent<HTMLInputElement>) { const file = event.target.files?.[0]; if (!file) return; if (originalUrl) URL.revokeObjectURL(originalUrl); setPreviewUrl((old) => { if (old) URL.revokeObjectURL(old); return ""; }); setImage(file); setOriginalUrl(URL.createObjectURL(file)); }
  async function openSourceDetails(source: Source) { setOpenSource(openSource === source.id ? null : source.id); if (!source.components) { try { const detail = await api<Source>(`/api/studio/sources/${source.id}`); setSources((all) => all.map((s) => s.id === source.id ? detail : s)); } catch (e) { setSourceError(String(e)); } } }
  async function useLibraryLook(look: { id: number; name: string }) {
    try {
      const source = await api<Source>(`/api/studio/sources/from-look/${look.id}`, { method: "POST" });
      const component = source.components?.find((item) => item.type === "cube_lut");
      if (!component) throw new Error(`${look.name} has no usable LUT component`);
      const layer: Layer = { id: id(), name: look.name, type: (component.type || "cube_lut").toLowerCase(), role: "base", source: source.filename, source_id: source.id, component_id: component.id || component.component_id, enabled: true, strength: 100 };
      setHistory((items) => [...items.slice(-29), graph]);
      setFuture([]);
      setGraph((current) => withBaseLayers(current, [layer], look.name));
      setSelectedLayer(layer.id);
      setSources((all) => all.some((item) => item.id === source.id) ? all : [source, ...all]);
      setView("studio");
    } catch (e) {
      setMessage(String(e));
    }
  }

  return <div className="app-shell">
    <aside><a className="brand" href="/"><span>FL</span><strong>Film Look<br />Studio</strong></a><nav>{[["studio", "Look Builder"], ["mylooks", "My Looks & workspaces"], ["library", "Leica library"], ["sources", "Source library"], ["inventory", "Provenance"], ["fuji", "Fuji recipes"]].map(([key, label]) => <button className={view === key ? "active" : ""} onClick={() => setView(key as View)} key={key}>{label}</button>)}</nav><div className="aside-foot"><span>{user?.firstName || user?.primaryEmailAddress?.emailAddress || "Signed in"}</span><button className="sign-out" onClick={() => signOut({ redirectUrl: "/" })}>Sign out</button><span><i className="online-dot" /> Leica Look Engine</span><a href="/look-building">How Looks are built</a><a href="/install-guide">Camera installation guide</a><a href="/docs">API documentation</a></div></aside>
    <main>{message && <div className="message" role="status">{message}</div>}{sourceError && <div className="error">{sourceError}</div>}
      {view === "studio" && <><div className="studio-head"><div><p className="eyebrow">Live color assembly bench / graph {graph.version}</p><h1>{graph.name}</h1></div><div className="head-actions"><button className="secondary" onClick={undo} disabled={!history.length}>Undo</button><button className="secondary" onClick={redo} disabled={!future.length}>Redo</button><button className="secondary" onClick={() => mutate({ ...graph, layers: initialLayers.map((l) => ({ ...l, id: id() })), controls: { ...defaultControls }, solo: null })}>Reset</button><span className="status-chip">{rendering ? "Rendering preview" : "Live preview"}</span></div></div>
        <div className="toolbar"><input value={graph.name} onChange={(e) => setGraph({ ...graph, name: e.target.value })} aria-label="Look name" /><label className="source-meta">Look ID <input type="number" min="1" value={graph.look_id} onChange={(e) => setGraph({ ...graph, look_id: Number(e.target.value) || 1142 })} /></label><select value={graph.base} onChange={(e) => setGraph({ ...graph, base: e.target.value })}><option>Standard</option><option>Monochrome</option></select><button className="secondary" onClick={saveWorkspace}>Save workspace</button><button className="secondary" onClick={saveLook}>Save to My Looks</button><button className="secondary" onClick={reviewGraph}>Verify 17³ LUT</button><button className="secondary" onClick={buildCube} disabled={status?.ready !== true}>Export CUBE</button><button className="primary" onClick={buildPackage} disabled={status?.ready !== true}>Build Look package</button></div>
        <div className="bench">
          <section className="bench-panel">
            <div className="panel-title">Film simulations <span>{profiles.length}</span></div>
            <div className="panel-body">
              <div className="source-tools">
                <input placeholder="Search brand, film, modification…" value={sourceSearch} onChange={(e) => setSourceSearch(e.target.value)} />
                <select value={sourceType} onChange={(e) => setSourceType(e.target.value)}><option value="">DCP + CUBE</option><option>DCP</option><option>CUBE</option></select>
                <label className="secondary">Bulk ingest sources<input type="file" multiple hidden accept=".dcp,.cube,.xmp,.lrtemplate,.jpg,.jpeg,.png" onChange={uploadSources} /></label>
              </div>
              <div className="source-list">
                <CatalogBrowser profiles={profiles} selectedId={selectedCatalogId} onSelect={useCatalogProfile} />
                {sources.map((source) => <div className={`source-row ${openSource === source.id ? "open" : ""}`} key={source.id} onClick={() => openSourceDetails(source)} ><strong>{source.display_name || source.filename || source.name || source.id}</strong><div className="source-meta">{source.type || source.asset_type || "SOURCE"} · {source.components?.length || 0} components</div>{openSource === source.id && <div className="component-list">{(source.components || []).map((component, index) => <div className="component-row" key={component.component_id || component.id || index} draggable={component.blendable !== false} onDragStart={(e) => { e.stopPropagation(); e.dataTransfer.setData("component", JSON.stringify({ ...component, source_id: source.id })); }}><span>{component.name || component.component_id || component.id || component.type}</span><button className="tiny" disabled={component.blendable === false} title={component.reason} onClick={(e) => { e.stopPropagation(); addComponent(component, source); }}>Use this</button></div>)}</div>}</div>)}
              </div>
            </div>
          </section>
          <section className="bench-panel"><div className="preview-toolbar"><div><b>VIEWFINDER</b> <span className="source-meta"> · {previewMode === "wipe" ? "draggable wipe" : "side by side"}</span></div><div className="head-actions"><label className="tiny">Upload test image<input type="file" hidden accept="image/jpeg,image/png,image/webp" onChange={chooseImage} /></label><button className="tiny" onClick={() => setPreviewMode("wipe")}>Wipe</button><button className="tiny" onClick={() => setPreviewMode("side")}>Side by side</button><button className={`tiny ${zoom === "fit" ? "active" : ""}`} onClick={() => setZoom("fit")}>Fit</button><button className={`tiny ${zoom === "100" ? "active" : ""}`} onClick={() => setZoom("100")}>100%</button></div></div><div className={`preview-stage ${previewMode === "side" ? "side-by-side" : ""}`}>{originalUrl ? previewMode === "side" ? <><div className="compare-pane"><img style={{ objectFit: zoom === "100" ? "none" : "contain" }} src={originalUrl} alt="Original" /><span className="preview-caption left">Original</span></div><div className="compare-pane"><img style={{ objectFit: zoom === "100" ? "none" : "contain" }} src={previewUrl || originalUrl} alt="Current look" /><span className="preview-caption right">{previewUrl ? "Current look" : rendering ? "Rendering…" : "Preview unavailable"}</span></div></> : <><img style={{ objectFit: zoom === "100" ? "none" : "contain" }} src={originalUrl} alt="Original" /><div className="wipe" style={{ clipPath: `inset(0 ${100 - wipe}% 0 0)` }}><img style={{ objectFit: zoom === "100" ? "none" : "contain" }} src={previewUrl || originalUrl} alt="Current look" /></div><span className="wipe-divider" style={{ left: `${wipe}%` }} /><span className="preview-caption left">{previewUrl ? "Current look" : rendering ? "Rendering…" : "Preview unavailable"}</span><span className="preview-caption right">Original</span><input className="wipe-range" aria-label="Wipe position" type="range" min="0" max="100" value={wipe} onChange={(e) => setWipe(Number(e.target.value))} /></> : <div className="empty-preview">Upload one test photograph. Every graph edit will arrive here without a compile step.</div>}</div><div className="filmstrip"><button>MY IMAGE</button><button disabled>Portrait / skin</button><button disabled>Landscape</button><button disabled>City / street</button><button disabled>Foliage</button><button disabled>HDR chart</button></div></section>
          <section className="bench-panel"><div className="panel-title">Look stack <span>{graph.layers.length} nodes</span></div><div className="panel-body"><div className="stack" onDragOver={(e) => e.preventDefault()} onDrop={(e) => { const raw = e.dataTransfer.getData("component"); if (raw) addComponent(JSON.parse(raw)); }}>{displayedLayers.map((layer, index) => <div className={`stack-row ${layer.enabled ? "" : "disabled"}`} key={layer.id} draggable onDragStart={(e) => e.dataTransfer.setData("layer", layer.id)} onDragOver={(e) => e.preventDefault()} onDrop={(e) => { const dragged = e.dataTransfer.getData("layer"); if (!dragged) return; e.stopPropagation(); const from = graph.layers.findIndex((item) => item.id === dragged); if (from >= 0) moveLayer(dragged, index - from); }} onClick={() => setSelectedLayer(layer.id)}><div className="stack-main"><span className="drag">::</span><input type="checkbox" checked={layer.enabled} onChange={(e) => updateLayer(layer.id, { enabled: e.target.checked })} /><span className="stack-name">{layer.name}</span><button title="Solo" onClick={() => setSoloLayer(solo === layer.id ? null : layer.id)}>S</button><button title="Move up" onClick={() => moveLayer(layer.id, -1)}>↑</button><button title="Move down" onClick={() => moveLayer(layer.id, 1)}>↓</button><button title="Duplicate" onClick={() => { const copy = { ...layer, id: id(), name: `${layer.name} copy` }; mutate({ ...graph, layers: [...graph.layers.slice(0, index + 1), copy, ...graph.layers.slice(index + 1)] }); }}>+</button><button title="Delete" onClick={() => mutate({ ...graph, layers: graph.layers.filter((l) => l.id !== layer.id) })}>×</button></div><div className="range-line"><span>strength</span><input type="range" min="0" max="200" value={layer.strength} onChange={(e) => updateLayerStrength(layer.id, Number(e.target.value))} /><span className="range-value">{layer.strength}%</span></div></div>)}</div><div className="inspector"><h3>{graph.layers.find((l) => l.id === selectedLayer)?.name || "Select a component"}</h3><div className="button-row"><button className="tiny" onClick={() => setSelectedLayer("")}>Close details</button><button className="tiny" onClick={() => { const l = graph.layers.find((x) => x.id === selectedLayer); if (l) updateLayer(l.id, { strength: 100 }); }}>Reset node</button></div></div><ManualControls controls={graph.controls} onChange={updateControl} /><div className="control-section"><summary>Snapshots / history</summary><div className="snapshot-row"><input placeholder="Snapshot name" value={snapshotName} onChange={(e) => setSnapshotName(e.target.value)} /><button className="tiny" onClick={() => { if (snapshotName.trim()) { setSnapshots([...snapshots, { name: snapshotName, graph }]); setSnapshotName(""); } }}>Save</button></div><div className="snapshot-list">{snapshots.map((s) => <button key={s.name} onClick={() => mutate(s.graph)}>{s.name}</button>)}</div></div><div className="target-card"><header><h3>Leica target</h3><span className={status?.ready === true ? "ready" : "dirty"}>{status?.ready === true ? "READY" : status ? "NEEDS ATTENTION" : "CHECKING"}</span></header><div className="target-line"><span>Name</span><b>{graph.name}</b></div><div className="target-line"><span>ID</span><b>{graph.look_id}</b></div><div className="target-line"><span>Base</span><b>{graph.base}</b></div><div className="target-line"><span>Compiler</span><b className={status?.ready === true ? "ready" : "dirty"}>{status?.ready === true ? "READY" : "NOT READY"}</b></div>{status?.ready === false && <p role="alert">{errorMessage(status.errors || status.unsupported)}</p>}<div className="target-line"><span>D860</span><b className="dirty">DIRTY / RECOMPILE</b></div></div></div></section>
        </div></>}
      {view === "sources" && <SourceLibrary sources={sources} uploadSources={uploadSources} search={sourceSearch} setSearch={setSourceSearch} type={sourceType} setType={setSourceType} open={openSource} openSource={openSourceDetails} add={addComponent} />}
      {view === "mylooks" && <MyLibrary workspaces={workspaces} looks={savedLooks} selected={selectedLooks} setSelected={setSelectedLooks} load={(saved) => { mutate(saved.graph); setView("studio"); }} download={downloadSelectedLooks} />}
      {view === "library" && <LegacyLibrary setView={setView} useLook={useLibraryLook} />}
      {view === "inventory" && <SimpleView title="Provenance" text="Immutable source and compiler inventory remains available from the original workflow." endpoint="/api/inventory" />}
      {view === "fuji" && <SimpleView title="Fuji Recipe Lab" text="Target-specific Fuji recipes remain separate from the non-destructive Leica graph." endpoint="/api/fuji/recipes" />}
    </main></div>;
}

function MyLibrary({ workspaces, looks, selected, setSelected, load, download }: {
  workspaces: SavedGraph[]; looks: SavedGraph[]; selected: string[];
  setSelected: (ids: string[]) => void; load: (saved: SavedGraph) => void; download: () => void;
}) {
  const toggle = (id: string) => setSelected(selected.includes(id) ? selected.filter((item) => item !== id) : [...selected, id]);
  return <><div className="studio-head"><div><p className="eyebrow">Private account library</p><h1>My Looks & workspaces</h1></div><button className="primary" disabled={!selected.length} onClick={download}>Download {selected.length || ""} selected package{selected.length === 1 ? "" : "s"}</button></div>
    <section className="saved-section"><h2>Workspaces</h2><p className="intro">Resume the complete editable graph, controls, and selected film base.</p><div className="saved-grid">{workspaces.length ? workspaces.map((item) => <article key={item.id}><span>WORKSPACE</span><h3>{item.name}</h3><small>{new Date(item.updated_at).toLocaleString()}</small><button className="secondary" onClick={() => load(item)}>Open workspace</button></article>) : <p className="empty-saved">No saved workspaces yet.</p>}</div></section>
    <section className="saved-section"><h2>My Looks</h2><p className="intro">Select up to nine Looks and download one installer for the entire selection. Each Look needs a distinct Look ID.</p><div className="saved-grid">{looks.length ? looks.map((item) => <article className={selected.includes(item.id) ? "selected" : ""} key={item.id}><label><input type="checkbox" checked={selected.includes(item.id)} disabled={!selected.includes(item.id) && selected.length >= 9} onChange={() => toggle(item.id)} /> Include in package</label><h3>{item.name}</h3><small>{new Date(item.updated_at).toLocaleString()}</small><button className="secondary" onClick={() => load(item)}>Open in builder</button></article>) : <p className="empty-saved">Save a Look from the builder to start your library.</p>}</div></section>
  </>;
}

function CatalogBrowser({ profiles, selectedId, onSelect }: { profiles: CatalogProfile[]; selectedId: string | null; onSelect: (profile: CatalogProfile) => void }) {
  const brands = useMemo(() => {
    const result = new Map<string, Map<string, CatalogProfile[]>>();
    for (const profile of profiles) {
      const stocks = result.get(profile.brand) || new Map<string, CatalogProfile[]>();
      stocks.set(profile.stock, [...(stocks.get(profile.stock) || []), profile]);
      result.set(profile.brand, stocks);
    }
    return [...result.entries()];
  }, [profiles]);
  return <>{brands.map(([brand, stocks]) => <section className="catalog-brand" key={brand}>
    <h3>{brand}</h3>
    {[...stocks.entries()].map(([stock, modifications]) => <div className="catalog-stock" key={stock}>
      <strong>{stock}</strong>
      <div className="catalog-modifications">{modifications.map((profile) => <button
        className={`catalog-modification ${selectedId === profile.catalog_id ? "selected" : ""}`}
        key={profile.catalog_id}
        onClick={() => onSelect(profile)}
        aria-pressed={selectedId === profile.catalog_id}
      ><span>{profile.modification}</span><small>{profile.asset_type.toUpperCase()}</small></button>)}</div>
    </div>)}
  </section>)}</>;
}

function ManualControls({ controls, onChange }: { controls: Record<string, number>; onChange: (key: string, value: number) => void }) {
  const groups: [string, string[]][] = [["Basic", ["exposure", "contrast", "highlights", "shadows", "whites", "blacks"]], ["Color", ["temperature", "tint", "saturation", "vibrance"]], ["Color grading", ["shadowHue", "shadowSat", "shadowLum", "midHue", "midSat", "highlightHue", "highlightSat", "balance"]], ["Film character", ["toe", "shoulder", "midContrast", "blackLift", "rolloff", "density"]], ["Monochrome", ["monoMix", "yellowFilter", "orangeFilter", "redFilter", "greenFilter"]]];
  return <>{groups.map(([title, keys]) => <details className="control-section" key={title} open={title === "Basic"}><summary>{title}</summary><div className="control-grid">{(keys as string[]).map((key) => <label key={key}>{key.replace(/[A-Z]/g, (m) => ` ${m}`).replace(/^./, (m) => m.toUpperCase())}<input type="range" min={key.toLowerCase().includes("hue") ? 0 : -100} max={key.toLowerCase().includes("hue") ? 360 : 100} value={controls[key] ?? 0} onChange={(e) => onChange(key, Number(e.target.value))} /><span>{controls[key] ?? 0}</span></label>)}</div></details>)}</>;
}
function SourceLibrary({ sources, uploadSources, search, setSearch, type, setType, open, openSource, add }: { sources: Source[]; uploadSources: (e: ChangeEvent<HTMLInputElement>) => void; search: string; setSearch: (s: string) => void; type: string; setType: (s: string) => void; open: string | null; openSource: (s: Source) => void; add: (c: Component, s?: Source) => void }) { return <><div className="studio-head"><div><p className="eyebrow">Color parts bin / immutable provenance</p><h1>Source Library</h1></div><label className="primary">Bulk ingest<input type="file" hidden multiple onChange={uploadSources} /></label></div><div className="library-shell"><div className="source-upload"><input placeholder="Search names and metadata" value={search} onChange={(e) => setSearch(e.target.value)} /><select value={type} onChange={(e) => setType(e.target.value)}><option value="">All source types</option><option>DCP</option><option>CUBE</option><option>XMP</option><option>LRTemplate</option><option>Hald</option><option>Leica Look</option></select></div><div className="source-list">{sources.map((s) => <div className={`source-row ${open === s.id ? "open" : ""}`} key={s.id} onClick={() => openSource(s)}><strong>{s.filename || s.name || s.id}</strong><div className="source-meta">{s.type || s.asset_type} · {s.provenance || "Provenance recorded"}</div>{open === s.id && <div className="component-list">{(s.components || []).map((c, i) => <div className="component-row" key={i}><span>{c.name || c.component_id || c.id || c.type}</span><button className="tiny" disabled={c.blendable === false} title={c.reason} onClick={(e) => { e.stopPropagation(); add(c, s); }}>Use this component</button></div>)}</div>}</div>)}</div></div></>; }
function LegacyLibrary({ setView, useLook }: { setView: (v: View) => void; useLook: (look: { id: number; name: string }) => void }) {
  const [looks, setLooks] = useState<{ id: number; name: string; base_name?: string }[]>([]);
  const [error, setError] = useState("");
  useEffect(() => { api<{ looks: { id: number; name: string; base_name?: string }[] }>("/api/library").then((data) => setLooks(data.looks)).catch((e) => setError(String(e))); }, []);
  return <><div className="studio-head"><div><p className="eyebrow">Existing workflow preserved</p><h1>Leica library</h1></div><button className="primary" onClick={() => setView("studio")}>Open Look Builder</button></div><p className="intro">Browse verified generic looks, inspect payloads, download packages, and use any look as a source component in the assembly bench.</p>{error && <div className="error">{error}</div>}<div className="source-grid">{looks.map((look) => <article key={look.id}><span>VERIFIED LOOK · {look.id}</span><h3>{look.name}</h3><p>{look.base_name || "Standard"} base · available in the original Leica workflow</p><div className="button-row"><a className="secondary" href={`/api/looks/${look.id}/icon?v=generic-1`}>Inspect icon</a><button className="tiny" onClick={() => useLook(look)}>Use in builder</button></div></article>)}</div></>;
}
function SimpleView({ title, text, endpoint }: { title: string; text: string; endpoint: string }) { return <><div className="studio-head"><div><p className="eyebrow">Film Look Studio / retained workflow</p><h1>{title}</h1></div></div><p className="intro">{text}</p><div className="payload-card"><p className="muted">Connected endpoint: <code>{endpoint}</code></p><p className="validation-line">Access preserved. Use the Look Builder for live graph work.</p></div></>; }
export default App;