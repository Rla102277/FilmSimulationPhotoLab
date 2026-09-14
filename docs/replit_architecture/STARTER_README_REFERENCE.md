# Infinite Arch Photo Lab — Replit Starter Bundle

This bundle is the canonical starting point for migrating the completed **Infinite Arch Leica Looks v1.2** system into a web-based **Infinite Arch Photo Lab** on Replit, then adding Fujifilm implementations.

## Ground truth

The immutable Leica baseline is:

`reference/leica/v1.2/Infinite_Arch_Leica_Looks_v1.2.zip`

SHA-256:

`1932cb619aeabe3b63bf616f77ffeac94181fa92af2a189f865068aac8f1e83f`

Do **not** reconstruct Leica v1.2 from chat summaries. Read the package itself. The actual v1.2 Look set is:

1. IA Invitation — 1001 — Monochrome
2. IA Witness — 1002 — Monochrome
3. IA Zone — 1003 — Monochrome
4. IA Presence — 1004 — Standard
5. IA Threshold — 1005 — Standard
6. IA American Negative — 1006 — Standard
7. IA Kin — 1007 — Standard
8. IA Natura — 1008 — Standard
9. IA Ember — 1009 — Standard

## Start here in Replit

1. Create a new Replit App.
2. Upload/import this entire ZIP.
3. Open `replit.md` and `AGENT_BOOTSTRAP_PROMPT.md`.
4. Give Replit Agent the contents of `AGENT_BOOTSTRAP_PROMPT.md` as its first instruction.
5. Tell Agent to run `python scripts/verify_authoritative.py` before changing Leica code.
6. Tell Agent to follow `docs/IMPLEMENTATION_ORDER.md` exactly.

## Product model

The application is **not a Leica uploader with Fuji bolted on**. It is a camera-independent color platform:

`Infinite Arch Look -> target implementation -> Leica / Fuji / software / DCP/XMP`

The Leica v1.2 system is the proven first target implementation. Fuji is the next target.

## Critical architecture rule

Replit/cloud code cannot directly reach the Leica camera at its private Wi-Fi address. Hardware communication therefore lives in the **IA Camera Bridge**, a small local process on the Mac. The web app and color intelligence live in Replit.
