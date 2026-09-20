"""Lazy catalog for the uploaded DCP/CUBE master archive."""

from __future__ import annotations

import hashlib
import os
import re
import zipfile
from functools import lru_cache
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARCHIVE = ROOT / "attached_assets" / "0_ALL_DCP_CUBE_LIBRARY_1789502493370.zip"
SUPPORTED = {".dcp": "dcp", ".cube": "cube"}
BRANDS = ("Agfa", "CineStill", "Edo", "Fujifilm", "Ilford", "Kodak", "Lomography", "Polaroid", "Rollei")


def _archive_path() -> Path:
    return Path(os.getenv("PROFILE_LIBRARY_ARCHIVE", str(DEFAULT_ARCHIVE)))


def _film_stock_name(member: str) -> str:
    path = PurePosixPath(member)
    name = path.parent.name if path.stem.lower() == "look" else path.stem
    camera_prefixes = (
        r"Canon EOS 5D\s+",
        r"LEICA M \(Typ 240\)\s+",
        r"M9 Digital Camera\s+",
    )
    for prefix in camera_prefixes:
        name = re.sub(rf"^{prefix}", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s*-\s*L$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s+L$", "", name, flags=re.IGNORECASE)

    slug_names = {
        "400h": "Fujifilm Pro 400H",
        "acros": "Fujifilm Neopan Acros 100",
        "cinestill50d": "CineStill 50D",
        "edo400": "Edo 400",
        "fortia": "Fujifilm Fortia",
        "hp5": "Ilford HP5 Plus",
        "portra": "Kodak Portra",
        "portranc": "Kodak Portra NC",
        "velvia": "Fujifilm Velvia",
        "vista": "Agfa Vista",
    }
    name = slug_names.get(name.lower(), name)
    fuji_recipes = {
        "ACROS": "Fujifilm Neopan Acros 100",
        "ASTIA": "Fujifilm Astia",
        "CLASSIC-Neg.": "Fujifilm Classic Negative",
        "PRO-Neg.Std": "Fujifilm Pro Negative · Standard",
        "Velvia": "Fujifilm Velvia",
    }
    recipe = re.fullmatch(r"FLog2_to_(.+)_33grid_V\.\d+\.\d+", name, re.IGNORECASE)
    if recipe:
        name = next((value for key, value in fuji_recipes.items() if key.casefold() == recipe.group(1).casefold()), name)

    manufacturer_rules = (
        (r"^(160S|400H)", "Fujifilm Pro "),
        (r"^(Astia|Fortia|Neopan|Provia|Sensia|Superia|T64|Velvia)", "Fujifilm "),
        (r"^(E100|E200|Ektachrome|Ektar|Elite|Gold|Kodachrome|Max|Plus-X|Portra|Portrait XPS|Royal|T-?MAX|TRI?-?X|Tri-X|UM)", "Kodak "),
        (r"^(Optima|Precisa|RSX|Ultra)", "Agfa "),
        (r"^(Delta|FP4|HP5|HPS|Pan F|XP2)", "Ilford "),
        (r"^(PX-|Time-Zero)", "Polaroid "),
    )
    if not re.match(r"^(Agfa|CineStill|Fujifilm|Fuji|Ilford|Kodak|Polaroid|Rollei)\b", name, re.I):
        for pattern, manufacturer in manufacturer_rules:
            if re.match(pattern, name, re.I):
                name = manufacturer + name
                break
    name = re.sub(r"^Fuji\b", "Fujifilm", name, flags=re.IGNORECASE)

    treatments = {
        "--": "−2 EV", "-": "−1 EV", "+": "+1 EV",
        "++": "+2 EV", "+++": "+3 EV",
    }
    match = re.search(r"\s+\d+\s*(--|-|\+{1,3})$", name)
    if match:
        name = name[:match.start()] + f" · {treatments[match.group(1)]}"
    else:
        match = re.search(r"([+-])(\d+)$", name)
        if match:
            sign, stops = match.groups()
            name = name[:match.start()] + f" · {sign}{stops} EV"
        elif path.suffix.lower() == ".cube" and re.search(r"\s2$", name):
            name = re.sub(r"\s2$", " · Standard", name)
    name = re.sub(r"\s+\b(?:XPRO|XP)\b", " · Cross Process", name, flags=re.IGNORECASE)
    name = re.sub(r"\s+\bNeg\b", " · Negative", name, flags=re.IGNORECASE)
    name = re.sub(r"\s+\bHC\b", " · High Contrast", name, flags=re.IGNORECASE)
    name = re.sub(r"\bGeneric\b", "Standard", name, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", name).strip(" ·")


def _catalog_labels(display_name: str) -> tuple[str, str, str]:
    main, separator, modification = display_name.partition(" · ")
    brand = next((item for item in BRANDS if main.casefold().startswith(item.casefold() + " ")), "Other")
    stock = main[len(brand):].strip() if brand != "Other" else main
    protected_stock = brand == "Fujifilm" and stock.casefold() in {"classic negative", "pro negative"}
    suffix = None if protected_stock else re.search(r"\s+(NC|VC|UC|Cross Process|Negative|High Contrast)$", stock, re.I)
    if suffix:
        stock = stock[:suffix.start()].strip()
        modification = " · ".join(filter(None, (suffix.group(1), modification)))
    return brand, stock, modification or "Standard"


def _preference(item: dict) -> tuple[int, str]:
    member = item["member"]
    if item["asset_type"] == "dcp":
        rank = 0 if "LEICA M (Typ 240)" in member else 1 if "M9 Digital Camera" in member else 2
    else:
        rank = 0 if "/02_CUBE/Archive/" in member else 1
    return rank, member


@lru_cache(maxsize=1)
def catalog() -> tuple[dict, ...]:
    archive = _archive_path()
    if not archive.exists():
        return ()
    raw = []
    with zipfile.ZipFile(archive) as bundle:
        for info in bundle.infolist():
            extension = PurePosixPath(info.filename).suffix.lower()
            if info.is_dir() or extension not in SUPPORTED:
                continue
            display_name = _film_stock_name(info.filename)
            brand, stock, modification = _catalog_labels(display_name)
            raw.append({
                "catalog_id": hashlib.sha256(info.filename.encode()).hexdigest()[:20],
                "member": info.filename,
                "asset_type": SUPPORTED[extension],
                "display_name": display_name,
                "brand": brand,
                "stock": stock,
                "modification": modification,
                "size": info.file_size,
            })
    grouped: dict[tuple[str, str], list[dict]] = {}
    for item in raw:
        grouped.setdefault((item["asset_type"], item["display_name"].casefold()), []).append(item)
    visible = []
    for variants in grouped.values():
        preferred = min(variants, key=_preference)
        visible.append({**preferred, "source_variant_count": len(variants)})
    return tuple(sorted(visible, key=lambda item: (
        item["brand"].casefold(), item["stock"].casefold(),
        item["modification"].casefold(), item["asset_type"],
    )))


def find_profile(catalog_id: str) -> dict | None:
    return next((dict(item) for item in catalog() if item["catalog_id"] == catalog_id), None)


def read_profile(profile: dict) -> bytes:
    with zipfile.ZipFile(_archive_path()) as bundle:
        return bundle.read(profile["member"])