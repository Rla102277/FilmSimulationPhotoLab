"""Public, generic film-style samples backed by immutable regression fixtures."""

SAMPLES = (
    {"id": 1201, "source_id": 1001, "key": "silver-grain", "name": "Silver Grain", "description": "Crisp monochrome with a firm toe and clear midtones."},
    {"id": 1202, "source_id": 1002, "key": "soft-portrait-mono", "name": "Soft Portrait Mono", "description": "Gentle monochrome contrast with open skin tones."},
    {"id": 1203, "source_id": 1003, "key": "deep-noir", "name": "Deep Noir", "description": "Dense blacks and dramatic monochrome separation."},
    {"id": 1204, "source_id": 1004, "key": "warm-negative", "name": "Warm Negative", "description": "Warm documentary color with restrained highlights."},
    {"id": 1205, "source_id": 1005, "key": "faded-chrome", "name": "Faded Chrome", "description": "Muted color, lifted shadows, and a weathered slide-film feel."},
    {"id": 1206, "source_id": 1006, "key": "cool-print", "name": "Cool Print", "description": "Cool shadows with balanced skin and clean whites."},
    {"id": 1207, "source_id": 1007, "key": "golden-400", "name": "Golden 400", "description": "Golden warmth, rounded contrast, and lively everyday color."},
    {"id": 1208, "source_id": 1008, "key": "natural-color", "name": "Natural Color", "description": "Neutral, moderate contrast and realistic saturation."},
    {"id": 1209, "source_id": 1009, "key": "amber-grain", "name": "Amber Grain", "description": "Amber highlights and rich, nostalgic color."},
)


def get_sample(sample_id: int) -> dict:
    for sample in SAMPLES:
        if sample["id"] == sample_id:
            return dict(sample)
    raise KeyError(f"Unknown film sample ID: {sample_id}")
