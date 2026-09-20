from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "reference" / "leica" / "v1.2" / "Infinite_Arch_Leica_Looks_v1.2.zip"
EXPECTED_SHA256 = "1932cb619aeabe3b63bf616f77ffeac94181fa92af2a189f865068aac8f1e83f"
MANIFEST_MEMBER = "Infinite_Arch_Leica_Looks_v1.2/looks_manifest.json"
ARCHIVE_PREFIX = "Infinite_Arch_Leica_Looks_v1.2/"


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


def archive_inventory() -> list[dict]:
    result = verify_authoritative_archive()
    if not result["ok"]:
        raise RuntimeError(f"Authoritative Leica archive failed integrity check: {result}")
    with zipfile.ZipFile(ARCHIVE) as zf:
        return [
            {
                "member": item.filename,
                "relative_path": item.filename.removeprefix(ARCHIVE_PREFIX),
                "size": item.file_size,
                "sha256": hashlib.sha256(zf.read(item)).hexdigest(),
                "classification": classify_member(item.filename),
            }
            for item in zf.infolist()
            if not item.is_dir()
        ]


def classify_member(member: str) -> str:
    relative = member.removeprefix(ARCHIVE_PREFIX)
    if relative == "looks_manifest.json":
        return "authoritative_manifest"
    if relative.startswith("looks/") and relative.endswith(".CUBE"):
        return "authoritative_cube"
    if relative.startswith("looks/") and relative.endswith(".bmp"):
        return "authoritative_icon"
    if relative.endswith((".py",)):
        return "known_good_installer"
    if relative.startswith(("analysis/", "Kin_Comparisons/")):
        return "analysis_or_reference"
    return "documentation_or_reference"


def get_authoritative_look(look_id: int) -> dict:
    for look in load_authoritative_manifest():
        if look["id"] == look_id:
            return look
    raise KeyError(f"Unknown authoritative Leica Look ID: {look_id}")


def read_look_asset(look_id: int, asset: str) -> bytes:
    if asset not in {"cube", "icon"}:
        raise ValueError("asset must be cube or icon")
    look = get_authoritative_look(look_id)
    member = ARCHIVE_PREFIX + look[asset]
    with zipfile.ZipFile(ARCHIVE) as zf:
        data = zf.read(member)
    expected_hash = look[f"{asset}_sha256"]
    if hashlib.sha256(data).hexdigest() != expected_hash:
        raise RuntimeError(f"Authoritative {asset} hash mismatch for Look {look_id}")
    return data


def read_authoritative_member(relative_path: str) -> bytes:
    result = verify_authoritative_archive()
    if not result["ok"]:
        raise RuntimeError(f"Authoritative Leica archive failed integrity check: {result}")
    member = ARCHIVE_PREFIX + relative_path.lstrip("/")
    with zipfile.ZipFile(ARCHIVE) as zf:
        return zf.read(member)
