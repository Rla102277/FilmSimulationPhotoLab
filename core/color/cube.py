from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import numpy as np
from PIL import Image, ImageOps


@dataclass(frozen=True)
class CubeLUT:
    title: str
    size: int
    domain_min: tuple[float, float, float]
    domain_max: tuple[float, float, float]
    values: np.ndarray

    def summary(self) -> dict:
        return {
            "title": self.title,
            "size": self.size,
            "rows": int(self.values.shape[0]),
            "domain_min": self.domain_min,
            "domain_max": self.domain_max,
            "value_min": float(self.values.min()),
            "value_max": float(self.values.max()),
            "order": "red-fast",
        }


def parse_cube(data: bytes) -> CubeLUT:
    text = data.decode("ascii", errors="strict")
    title = ""
    size = None
    domain_min = (0.0, 0.0, 0.0)
    domain_max = (1.0, 1.0, 1.0)
    rows: list[tuple[float, float, float]] = []
    for raw_line in text.splitlines():
        line = raw_line.split("#",1)[0].strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        keyword = parts[0].upper()
        if keyword == "TITLE":
            title = line.partition(" ")[2].strip().strip('"')
        elif keyword == "LUT_3D_SIZE":
            size = int(parts[1])
        elif keyword == "DOMAIN_MIN":
            domain_min = tuple(float(value) for value in parts[1:4])
        elif keyword == "DOMAIN_MAX":
            domain_max = tuple(float(value) for value in parts[1:4])
        else:
            if len(parts) != 3:
                raise ValueError(f"Invalid CUBE row: {line}")
            row = tuple(float(value) for value in parts)
            if not np.isfinite(row).all():
                raise ValueError("CUBE rows must be finite")
            rows.append(row)
    if size is None or not 2 <= size <= 256:
        raise ValueError(f"Invalid or missing LUT_3D_SIZE: {size}")
    if len(rows) != size**3:
        raise ValueError(f"Expected {size**3} rows, found {len(rows)}")
    if len(domain_min)!=3 or len(domain_max)!=3 or not np.isfinite([domain_min,domain_max]).all() or np.any(np.asarray(domain_max)<=np.asarray(domain_min)):
        raise ValueError("CUBE domain must have three finite increasing ranges")
    return CubeLUT(title, size, domain_min, domain_max, np.asarray(rows, dtype=np.float32))


def resample_cube(cube: CubeLUT, target_size: int = 17) -> CubeLUT:
    if not 2 <= target_size <= 256:
        raise ValueError("Target CUBE size must be between 2 and 256")
    if cube.size == target_size:
        return cube
    axis = np.linspace(0, cube.size - 1, target_size, dtype=np.float32)
    output = []

    def sample(red: float, green: float, blue: float) -> np.ndarray:
        low = np.floor([red, green, blue]).astype(int)
        high = np.minimum(low + 1, cube.size - 1)
        fr, fg, fb = np.asarray([red, green, blue]) - low

        def value(r: int, g: int, b: int) -> np.ndarray:
            return cube.values[b * cube.size * cube.size + g * cube.size + r]

        c00 = value(low[0], low[1], low[2]) * (1 - fr) + value(high[0], low[1], low[2]) * fr
        c01 = value(low[0], low[1], high[2]) * (1 - fr) + value(high[0], low[1], high[2]) * fr
        c10 = value(low[0], high[1], low[2]) * (1 - fr) + value(high[0], high[1], low[2]) * fr
        c11 = value(low[0], high[1], high[2]) * (1 - fr) + value(high[0], high[1], high[2]) * fr
        return (c00 * (1 - fg) + c10 * fg) * (1 - fb) + (c01 * (1 - fg) + c11 * fg) * fb

    for blue in axis:
        for green in axis:
            for red in axis:
                output.append(sample(float(red), float(green), float(blue)))
    return CubeLUT(cube.title, target_size, cube.domain_min, cube.domain_max, np.asarray(output, dtype=np.float32))


def serialize_leica_cube(cube: CubeLUT, look_id: int, name: str, base: int) -> bytes:
    # Bake domain mapping into the Leica unit input domain, even for a 17-grid source.
    axis=np.linspace(0,1,17)
    points=np.array([(r,g,b) for b in axis for g in axis for r in axis])
    values = np.clip(sample_cube(points,cube),0,1)
    if base == 1:
        luminance = (
            values[:, 0:1] * 0.2126
            + values[:, 1:2] * 0.7152
            + values[:, 2:3] * 0.0722
        )
        values = np.repeat(luminance, 3, axis=1)
    mode = "Monochrome" if base == 1 else "Standard"
    lines = [
        f"#Unique Leica Look ID: {look_id}",
        f"#Based Filmstyle Mode: {mode}",
        f'TITLE "{name}"',
        "LUT_3D_SIZE 17",
        "DOMAIN_MIN 0.0 0.0 0.0",
        "DOMAIN_MAX 1.0 1.0 1.0",
    ]
    lines.extend(" ".join(f"{float(value):.6f}" for value in row) for row in values)
    return ("\n".join(lines) + "\n").encode("ascii")


def parse_hald(data: bytes) -> CubeLUT:
    image = Image.open(BytesIO(data))
    if image.format == "TIFF":
        import tifffile
        values = tifffile.imread(BytesIO(data))
    else:
        values = np.asarray(image)
    if values.ndim!=3 or values.shape[2] not in (3,4):
        raise ValueError("Hald must contain RGB channels")
    height,width=values.shape[:2]
    level=round(width**(1/3))
    if height!=width or level<2 or level**3!=width:
        raise ValueError("Image dimensions do not form a standard Hald CLUT")
    if np.issubdtype(values.dtype,np.integer):
        values=values.astype(float)/np.iinfo(values.dtype).max
    else: values=values.astype(float)
    values=values[...,:3].reshape(-1,3)
    if not np.isfinite(values).all(): raise ValueError("Hald contains non-finite samples")
    return CubeLUT("Imported Hald CLUT",level**2,(0.,0.,0.),(1.,1.,1.),values)


def sample_cube(pixels: np.ndarray, cube: CubeLUT) -> np.ndarray:
    q=np.clip((pixels-np.asarray(cube.domain_min))/(np.asarray(cube.domain_max)-np.asarray(cube.domain_min)),0,1)*(cube.size-1)
    lo=np.floor(q).astype(np.int64);hi=np.minimum(lo+1,cube.size-1);f=q-lo;out=np.zeros_like(pixels,dtype=float)
    for b in (0,1):
        for g in (0,1):
            for r in (0,1):
                bits=np.array([r,g,b]);ix=np.where(bits,hi,lo);w=np.prod(np.where(bits,f,1-f),axis=-1)
                out+=cube.values[ix[...,2]*cube.size**2+ix[...,1]*cube.size+ix[...,0]]*w[...,None]
    return out


def display_image(image_data: bytes):
    from PIL import ImageCms
    image=ImageOps.exif_transpose(Image.open(BytesIO(image_data)))
    icc=image.info.get("icc_profile")
    if icc:
        try:
            image=ImageCms.profileToProfile(image,ImageCms.ImageCmsProfile(BytesIO(icc)),ImageCms.createProfile("sRGB"),outputMode="RGB")
        except Exception as exc: raise ValueError("Cannot convert embedded image color profile to sRGB") from exc
    return image.convert("RGB")


def apply_cube_to_image(image_data: bytes, cube: CubeLUT, max_dimension: int = 1600) -> bytes:
    image=display_image(image_data);image.thumbnail((max_dimension,max_dimension),Image.Resampling.LANCZOS)
    pixels=np.asarray(image,dtype=float)/255
    output=sample_cube(pixels,cube)
    rendered=Image.fromarray(np.uint8(np.clip(output,0,1)*255+.5))
    buffer=BytesIO();rendered.save(buffer,format="JPEG",quality=94,optimize=True)
    return buffer.getvalue()
