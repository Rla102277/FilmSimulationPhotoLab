from fastapi.responses import HTMLResponse


def look_building_page() -> HTMLResponse:
    return HTMLResponse(
        """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>How a Look is Built · Film Look Studio</title>
  <style>
    :root { color-scheme: dark; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }
    * { box-sizing: border-box; }
    body { margin: 0; background: #11110f; color: #f2efe8; }
    main { width: min(900px, calc(100% - 32px)); margin: 0 auto; padding: 56px 0 80px; }
    a { color: #d8ba7e; text-decoration: none; }
    a:hover { text-decoration: underline; }
    .back { color: #aaa59b; font-size: .9rem; }
    .eyebrow { margin-top: 48px; color: #c7a76c; letter-spacing: .16em; text-transform: uppercase; font-size: .75rem; }
    h1 { margin: 12px 0 16px; font: 500 clamp(2.5rem, 7vw, 5rem)/.95 Georgia, serif; }
    .lede { max-width: 720px; color: #b8b3aa; font-size: 1.08rem; line-height: 1.65; }
    .section { margin-top: 42px; padding-top: 28px; border-top: 1px solid #2f2d29; }
    h2 { margin: 0 0 12px; font: 500 1.7rem Georgia, serif; }
    h3 { margin: 24px 0 8px; font-size: 1rem; }
    p, li { color: #b8b3aa; line-height: 1.7; }
    ul, ol { padding-left: 1.25rem; }
    li { margin: 7px 0; }
    code { color: #d9d4ca; }
    pre { overflow-x: auto; padding: 18px; border: 1px solid #2f2d29; border-radius: 12px; background: #191816; color: #d9d4ca; line-height: 1.6; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; }
    .card { padding: 20px; border: 1px solid #2f2d29; border-radius: 12px; background: #191816; }
    .card h3 { margin-top: 0; color: #f2efe8; }
    .note { padding: 16px 18px; border-left: 3px solid #c7a76c; background: #191816; }
  </style>
</head>
<body>
  <main>
     <a class="back" href="/">← Back to Film Look Studio</a>
    <div class="eyebrow">Build notes</div>
    <h1>How a Look<br>is built</h1>
    <p class="lede">A Look starts as visual intent, becomes a target-specific color transform, and is complete for download only after the generated payload has been parsed and verified against its requested properties.</p>

    <section class="section">
      <h2>One Look, multiple implementations</h2>
      <p>A generic film concept can have separate implementations for Leica Q3/Q3 43, Fuji bodies, software/CUBE, and Lightroom/DCP. The visual family and each camera implementation are versioned separately.</p>
    </section>

    <section class="section">
      <h2>1. Define the visual intent</h2>
      <p>Set the intended contrast, highlight and shadow behavior, saturation, warmth or coolness, monochrome behavior, color bias, tone curve, and any effects the target can support. Reference images and film/profile research inform the decision, but the result must document its limits and provenance.</p>
    </section>

    <section class="section">
      <h2>2. Build the color transform</h2>
      <p>For the Leica implementation, the transform is a 17×17×17 3D LUT: 4,913 RGB entries mapping input color to output color.</p>
      <pre>RGB input
  → luminance
  → saturation adjustment
  → warmth adjustment
  → contrast
  → highlight/shadow shaping
  → clamped RGB output</pre>
      <p>The LUT must declare <code>LUT_3D_SIZE 17</code>, use a 0–1 domain, contain exactly 4,913 rows, and keep every output value between 0 and 1.</p>
    </section>

    <section class="section">
      <h2>3. Use Leica’s row order</h2>
      <p>The Q3 expects red-fast ordering. Red changes fastest, then green, then blue:</p>
      <pre>for blue in range(17):
    for green in range(17):
        for red in range(17):
            write(red, green, blue)</pre>
      <p>The project confirmed this with a deliberately obvious constant-magenta regression test after an earlier neutral-looking result exposed the wrong row order.</p>
    </section>

    <section class="section">
      <h2>4. Package the Leica payload</h2>
      <p>A Leica upload is not just a CUBE file. The known-good payload contains six property records:</p>
      <div class="grid">
        <div class="card"><h3><code>D861</code></h3><p>The numeric Look ID.</p></div>
        <div class="card"><h3><code>DC44</code></h3><p>UTF-16 Look name.</p></div>
        <div class="card"><h3><code>DC86</code></h3><p>180×90, 1-bit BMP icon.</p></div>
        <div class="card"><h3><code>D860</code></h3><p>Plaintext 17³ CUBE data.</p></div>
        <div class="card"><h3><code>D864</code></h3><p>Look type, 2 in the working payloads.</p></div>
        <div class="card"><h3><code>D866</code></h3><p>Base style: Standard or Monochrome.</p></div>
      </div>
    </section>

    <section class="section">
      <h2>5. Compile, parse, and verify</h2>
      <ul>
        <li>Verify CUBE and icon SHA-256 hashes.</li>
        <li>Check metadata, dimensions, row count, range, and red-fast behavior.</li>
        <li>Confirm monochrome or color behavior matches the declared base.</li>
        <li>Decode the generated six-field payload and compare all six properties, data types, order, lengths, and asset hashes.</li>
        <li>Keep the authoritative v1.2 ZIP untouched.</li>
      </ul>
    </section>

    <section class="section">
      <h2>6. Download the validated artifact</h2>
      <p>Film Look Studio returns the verified six-property payload as a downloadable binary. Packs also include the source CUBEs, icons, local injector, instructions, and a checksum manifest.</p>
      <ol>
        <li>Compile the requested fields using the authoritative v1.2 binary representation.</li>
        <li>Parse the newly generated payload.</li>
        <li>Compare ID, name, icon, CUBE, type, base, field order, and hashes.</li>
        <li>Enable download only when every check passes.</li>
      </ol>
      <p class="note">The evidence proves the payload binary used by the v1.2 writer. It does not prove an official SD-card import container or filename convention, so Photo Lab does not claim one.</p>
    </section>

    <section class="section note">
      <strong>Current project status:</strong>
      <p>The authoritative Leica library, editor, payload inspector, software preview, compiler, compile-parse verification, and pack download are active. The v1.2 archive is never edited.</p>
    </section>
  </main>
</body>
</html>
"""
    )


def install_guide_page() -> HTMLResponse:
    return HTMLResponse(
        """
<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Camera Installation Guide · Film Look Studio</title>
<style>:root{color-scheme:dark;font-family:Inter,system-ui,sans-serif}*{box-sizing:border-box}body{margin:0;background:#10110e;color:#eeeae1}main{width:min(920px,calc(100% - 32px));margin:auto;padding:54px 0 90px}a{color:#d2b474}h1{font:500 clamp(2.6rem,7vw,5rem)/1 Georgia,serif;margin:16px 0}.lede,p,li{color:#aaa79f;line-height:1.7}.step{margin:18px 0;padding:22px;border:1px solid #302f2a;border-radius:12px;background:#181915}.step b{color:#eeeae1}.warn{padding:18px;border-left:3px solid #d2b474;background:#1b1914}code,pre{color:#e7d3aa;background:#0b0c0a}pre{padding:16px;border-radius:8px;overflow:auto}h2{margin-top:42px;font:500 1.8rem Georgia,serif}</style></head>
<body><main><a href="/">← Back to Film Look Studio</a><h1>Install a Look on Leica Q3 / Q3 43</h1>
<p class="lede">These instructions match the injector included in each downloaded package. The website never connects to your camera. The downloaded Python script runs locally and uses the previously proven Leica FOTOS-assisted PTP/IP handoff.</p>
<p class="warn"><b>Important:</b> This is a reverse-engineered workflow, not an official Leica import method. Charge the camera, do not interrupt a write, and inspect the camera before rerunning after any ambiguous network failure.</p>
<h2>Before you begin</h2>
<div class="step"><b>1. Prepare the computer.</b><p>Install Python 3. Extract the entire downloaded ZIP into one folder. Do not move only <code>injector.py</code>; it needs the manifest, CUBE, icon, and payload files beside it.</p></div>
<div class="step"><b>2. Validate without connecting.</b><pre>cd /path/to/extracted-package
python3 injector.py --list</pre><p>Continue only if every Look prints <b>PASS</b> and the script ends with “VALIDATION ONLY.” This command performs no camera connection or write.</p></div>
<div class="step"><b>3. Make room in the camera.</b><p>A Q3-family camera has nine downloadable Look slots in the proven workflow. In Leica FOTOS, remove downloadable Looks you do not need. The injector safely stops if non-matching downloaded Looks are present.</p></div>
<div class="step"><b>4. Establish the authorized FOTOS state.</b><p>Turn on the camera, enable its normal Leica FOTOS connectivity, and connect with the Leica FOTOS app as you normally do. Confirm FOTOS can see the camera.</p></div>
<div class="step"><b>5. Keep the camera network connection.</b><p>Keep the computer or Python-capable device on the camera’s network. Force-quit or fully close FOTOS so it releases its sockets while leaving the authenticated camera session in the known working state.</p></div>
<div class="step"><b>6. Run the local injector.</b><pre>python3 injector.py</pre><p>The script waits for the camera, initializes the inherited session, and stops before writing unless the expected session and current Look table can be read.</p></div>
<div class="step"><b>7. Watch each verification.</b><p>For each missing Look, the injector uploads once, reads the Look table again, and checks the exact ID, name, type, and base. Success is reported as <b>VERIFIED</b>. A final <b>SUCCESS</b> means the package was installed and re-read.</p></div>
<div class="step"><b>8. Confirm on the camera.</b><p>Open the Leica Look selection on the camera and confirm the new name and icon appear. Make test photographs before depending on the Look for important work.</p></div>
<h2>If it stops</h2><ul>
<li><b>SessionAlreadyOpen / 0x201E:</b> this is expected in the proven FOTOS handoff and is accepted by the injector.</li>
<li><b>SAFE STOP:</b> no write occurred. Follow the printed instruction, usually removing conflicting downloadable Looks or re-establishing FOTOS.</li>
<li><b>TIMEOUT BEFORE WRITE:</b> the camera/session was not found; no upload was attempted.</li>
<li><b>AMBIGUOUS WRITE STATE:</b> do not immediately rerun. Inspect the camera’s Look list first.</li>
<li><b>0x2001:</b> this is the known successful Leica operation response used by the injector.</li>
</ul>
<h2>Fujifilm cameras</h2><p>Leica payloads and the Python injector are not compatible with Fujifilm cameras. Fuji output in this app is a human-readable recipe. Enter supported settings manually in the camera menu and verify them against the exact body and firmware; the app does not claim an automated Fuji installer.</p>
</main></body></html>"""
    )