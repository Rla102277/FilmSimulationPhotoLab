# Infinite Arch Photo Lab — Replit migration

This bundle preserves the complete local Codex work that led to working custom
Leica Looks and places the authoritative final package at the center of a
Replit-ready project.

## Ground truth

The immutable Leica release is:

`reference/leica/v1.2/Infinite_Arch_Leica_Looks_v1.2.zip`

Expected SHA-256:

`1932cb619aeabe3b63bf616f77ffeac94181fa92af2a189f865068aac8f1e83f`

Never edit or regenerate that ZIP. Work from the extracted copy under
`working/Infinite_Arch_Leica_Looks_v1.2/` and preserve regression fixtures.

Run `python main.py` after importing this bundle into Replit. It performs an
offline integrity check and prints the authoritative nine-Look manifest. It
does not contact or modify a camera.

## Authoritative v1.2 lineup

| ID | Name | Base |
|---:|---|---|
| 1001 | IA Invitation | Monochrome |
| 1002 | IA Witness | Monochrome |
| 1003 | IA Zone | Monochrome |
| 1004 | IA Presence | Standard |
| 1005 | IA Threshold | Standard |
| 1006 | IA American Negative | Standard |
| 1007 | IA Kin | Standard |
| 1008 | IA Natura | Standard |
| 1009 | IA Ember | Standard |

## What is included

- `reference/`: immutable authoritative Leica v1.2 release.
- `working/`: extracted v1.2 working copy.
- `source/confirmed_python/`: the successful session-inheritance, official
  Bleach, magenta proof, corrected Presence, and first-custom-test code.
- `source/pcap_tools/`: parsers used to reconstruct PTP/IP and Leica payloads.
- `source/swift_cli/`: the complete Swift CLI/Xcode source from the last local
  network-probe build.
- `source/generators/`: local LUT and library generators.
- `source/candidate_film_set/`: the four-film candidate set produced after the
  custom-LUT execution proof.
- `source/experimental_legacy_banks/`: superseded bank experiments. Do not run.
- `codex_outputs/`: the complete user-facing Codex output archive, including
  packet captures, decoded traces, reports, settings backups, source ZIPs and
  prior deliverables.
- `docs/PROJECT_STATE.md`: technical handoff and confirmed findings.
- `AGENT_BOOTSTRAP_PROMPT.md`: first instructions for Replit Agent.

## Architecture boundary

Replit can host the library, compiler, previews, manifests, regression tests,
job queue and web interface. It cannot reach a Q3 at `192.168.54.1` on private
camera Wi-Fi. Actual camera traffic belongs in a small local Mac/iPhone bridge
that initiates an outbound authenticated connection to the Replit service.

Keep the Repl private. Packet captures and settings backups contain camera and
network identifiers.

