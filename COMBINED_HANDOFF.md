# Combined Codex + Replit handoff

This bundle uses `Infinite_Arch_Photo_Lab_Replit_Migration_2026-09-14.zip` as the
primary codebase because it contains the complete recovered Codex work: confirmed
Python camera experiments, packet captures, PCAP tools, Swift CLI source,
generators, settings backups, reports, and the full extracted Leica v1.2 working
tree.

The earlier Replit starter has been merged **only as non-destructive web/product
scaffolding**. It did not overwrite any migration/Codex file.

## Authority order

1. `reference/leica/v1.2/Infinite_Arch_Leica_Looks_v1.2.zip` — immutable Leica ground truth.
2. Existing migration/Codex source and tests — preserve confirmed behavior.
3. `working/Infinite_Arch_Leica_Looks_v1.2/` — extracted working copy.
4. Replit web/bridge scaffolding — architecture to wrap the proven system.
5. Historical experiments — forensic/reference only unless explicitly promoted.

## Added from the Replit starter

- `server/` — initial FastAPI service scaffold.
- `bridge/` — initial local IA Camera Bridge scaffold.
- `core/` — shared package skeleton for future color/look modules.
- `camera_profiles/` — initial Leica/Fuji capability definitions.
- `docs/replit_architecture/` — web architecture, bridge protocol, data model,
  Fuji roadmap, implementation order, guardrails, and setup notes.
- `.env.example`, `pyproject.toml`, `replit.md`, `seed/` and helper scripts.

These additions are scaffolding. They must be adapted around the proven Codex
implementation rather than replacing it.

## First action in Replit

Run:

```bash
python main.py
python -m unittest discover -s tests -p 'test_*.py'
```

Both must pass before refactoring Leica code.

Then read:

1. `START_HERE.md`
2. `docs/PROJECT_STATE.md`
3. `AGENT_BOOTSTRAP_PROMPT.md`
4. `docs/replit_architecture/ARCHITECTURE.md`

Do not begin Fuji protocol reverse engineering until Leica v1.2 regression parity
is green behind the new service/bridge boundaries.
