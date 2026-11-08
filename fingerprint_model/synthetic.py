"""Original procedural ridge motifs, not anatomically validated fingerprints.

Arch: open ridges crossing left/right with a central hump.
Loop: recurving open U ridges; no closed ellipse at the chosen level sets.
Whorl: concentric closed oval ridges. No actual person or external data.
"""
import csv
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .core import LABELS, SIZE


def motif(label, identity_seed, impression_seed):
    base = np.random.default_rng(identity_seed)
    aug = np.random.default_rng(impression_seed)
    axis = np.linspace(-1, 1, SIZE)
    x, y = np.meshgrid(axis, axis)
    angle = aug.uniform(-0.22, 0.22)
    x, y = (x * np.cos(angle) - y * np.sin(angle),
            x * np.sin(angle) + y * np.cos(angle))
    x = (x - base.uniform(-0.12, 0.12) - aug.uniform(-0.025, 0.025)) / base.uniform(0.85, 1.15)
    y = (y - base.uniform(-0.12, 0.12) - aug.uniform(-0.025, 0.025)) / base.uniform(0.85, 1.15)
    frequency = base.uniform(8.0, 12.0)
    shift = base.uniform(0, 2 * np.pi)
    if label == "arch":
        phase = y + base.uniform(0.3, 0.7) * np.exp(-x * x / base.uniform(0.25, 0.6))
    elif label == "loop":
        # k>1 gives open conic curves, rather than the k<1 closed ellipses.
        # Slight tilt gives left/right-facing variants without changing labels.
        tilt = base.choice([-1, 1]) * base.uniform(0.20, 0.45)
        u, v = x * np.cos(tilt) - y * np.sin(tilt), x * np.sin(tilt) + y * np.cos(tilt)
        v = v + 0.2
        phase = np.sqrt(u * u + v * v + 0.004) + base.uniform(1.08, 1.22) * v
    elif label == "whorl":
        phase = np.sqrt(x * x + y * y / base.uniform(0.8, 1.2) + 0.01)
    else:
        raise ValueError(label)
    ridge = 0.5 + 0.5 * np.cos(2 * np.pi * frequency * phase + shift)
    # Identical nuisance distribution for all classes; no label-coded brightness/noise.
    image = 0.5 + aug.uniform(0.5, 0.8) * (ridge - 0.5)
    image += aug.uniform(-0.09, 0.09) * x + aug.uniform(-0.09, 0.09) * y
    image += aug.normal(0, aug.uniform(0.008, 0.025), image.shape)
    im = Image.fromarray(np.uint8(np.clip(image, 0, 1) * 255))
    return im.filter(ImageFilter.GaussianBlur(aug.uniform(0.15, 0.6)))


def generate(out, identities=120, impressions=4, seed=20261108):
    if identities < 10 or impressions < 1:
        raise ValueError("Use >=10 identities per class and >=1 impression")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    rng = np.random.default_rng(seed)
    rows = []
    for label in LABELS:
        # Assign splits at base identity level BEFORE creating impressions.
        order = rng.permutation(identities)
        for rank, number in enumerate(order):
            split = "train" if rank < int(identities * .7) else "validation" if rank < int(identities * .85) else "test"
            identity_seed = int(rng.integers(0, 2**31))
            group = f"{label}-{number:04d}"
            folder = out / "images" / group
            folder.mkdir(parents=True)
            for j in range(impressions):
                imp_seed = int(rng.integers(0, 2**31))
                relative = Path("images") / group / f"{j:02d}.png"
                motif(label, identity_seed, imp_seed).save(out / relative)
                rows.append({"path": relative.as_posix(), "label": label, "group_id": group,
                             "split": split, "source": "synthetic", "license": "project-MIT-original-synthetic",
                             "provenance": "procedural-motif-v1", "identity_seed": identity_seed,
                             "impression_seed": imp_seed})
    with (out / "manifest.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    contact = Image.new("RGB", (6 * SIZE, 3 * (SIZE + 25)), "white")
    draw = ImageDraw.Draw(contact)
    for row, label in enumerate(LABELS):
        selected = [r for r in rows if r["label"] == label and r["path"].endswith("00.png")][:6]
        for col, item in enumerate(selected):
            with Image.open(out / item["path"]) as im:
                contact.paste(im, (col * SIZE, row * (SIZE + 25) + 25))
            draw.text((col * SIZE + 4, row * (SIZE + 25) + 5), label + " / synthetic", fill="black")
    contact.save(out / "contact-sheet.png")
    return out / "manifest.csv"
