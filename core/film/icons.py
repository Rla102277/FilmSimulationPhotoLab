from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw, ImageFont


def generic_film_icon(name: str) -> bytes:
    """Create the exact positive-orientation 180×90 1-bit BMP used by Leica packages."""
    words = [word for word in name.upper().split() if word]
    initials = "".join(word[0] for word in words[:3]) or "FL"
    image = Image.new("1", (180, 90), 0)
    draw = ImageDraw.Draw(image)
    draw.rectangle((3, 3, 176, 86), outline=1, width=2)
    font = ImageFont.load_default(size=22)
    box = draw.textbbox((0, 0), initials, font=font)
    x = (180 - (box[2] - box[0])) // 2
    y = (90 - (box[3] - box[1])) // 2 - 2
    draw.text((x, y), initials, fill=1, font=font)
    output = BytesIO()
    image.save(output, format="BMP")
    data = output.getvalue()
    if len(data) > 2224:
        raise ValueError("Generated Leica icon exceeds the proven size")
    return data + (b"\x00" * (2224 - len(data)))