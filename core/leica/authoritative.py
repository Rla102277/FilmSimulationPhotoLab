from pathlib import Path
import hashlib, json, zipfile

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "reference" / "leica" / "v1.2" / "Infinite_Arch_Leica_Looks_v1.2.zip"
EXPECTED_SHA256 = "1932cb619aeabe3b63bf616f77ffeac94181fa92af2a189f865068aac8f1e83f"
MANIFEST_MEMBER = "Infinite_Arch_Leica_Looks_v1.2/looks_manifest.json"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_authoritative_archive() -> dict:
    if not ARCHIVE.exists():
        return {"ok": False, "error": "archive_missing", "path": str(ARCHIVE)}
    actual = sha256_file(ARCHIVE)
    ok = actual == EXPECTED_SHA256
    return {"ok": ok, "expected_sha256": EXPECTED_SHA256, "actual_sha256": actual, "path": str(ARCHIVE)}


def load_authoritative_manifest() -> list[dict]:
    result = verify_authoritative_archive()
    if not result["ok"]:
        raise RuntimeError(f"Authoritative Leica archive failed integrity check: {result}")
    with zipfile.ZipFile(ARCHIVE) as zf:
        return json.loads(zf.read(MANIFEST_MEMBER))
