"""Manifest validation: grouping and exact-image duplicate protection."""
import csv
import hashlib
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from .core import LABELS, features, load_image, map_label, quality


def duplicate_connected_groups(records):
    """Conservatively join source groups linked by identical decoded image pixels.

    records: iterable of (local image path, source group ID). No labels inferred.
    Returned mapping must be applied BEFORE assigning dataset splits.
    """
    parents, hashes = {}, {}
    count = 0
    def root(group):
        parents.setdefault(group, group)
        while parents[group] != group:
            parents[group] = parents[parents[group]]
            group = parents[group]
        return group
    for path, group in records:
        root(group)
        with Image.open(path) as image:
            image = ImageOps.exif_transpose(image).convert("L")
            digest = hashlib.sha256(str(image.size).encode() + image.tobytes()).hexdigest()
        if digest in hashes:
            first, second = root(group), root(hashes[digest])
            parents[max(first, second)] = min(first, second)
        else:
            hashes[digest] = group
        count += 1
    return {g: root(g) for g in parents}, {"images": count, "unique_decoded_images": len(hashes),
            "source_groups": len(parents), "connected_groups": len({root(g) for g in parents})}


def read_manifest(path, preprocessing="none", excluded_splits=()):
    path = Path(path).resolve()
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError("empty_manifest")
    required = {"path", "label", "group_id", "split", "source", "license", "provenance"}
    group_splits, hash_splits, seen_paths = {}, {}, set()
    prepared = []
    for row in rows:
        if not required.issubset(row) or any(not row[k].strip() for k in required):
            raise ValueError("missing_required_manifest_fields")
        if row["split"] not in {"train", "validation", "test"}:
            raise ValueError("invalid_split")
        if row["source"] not in {"synthetic", "real"}:
            raise ValueError("invalid_source")
        label = map_label(row["label"])
        file = (path.parent / row["path"]).resolve()
        if not file.is_relative_to(path.parent):
            raise ValueError("image_path_must_be_inside_manifest_directory")
        if file in seen_paths:
            raise ValueError("duplicate_image_path")
        seen_paths.add(file)
        split, group = row["split"], row["group_id"]
        if group in group_splits and group_splits[group] != split:
            raise ValueError("group_leakage")
        group_splits[group] = split
        if split in excluded_splits:
            continue
        image = load_image(file, preprocessing=preprocessing)
        # Decoded normalized pixels catch a renamed/re-encoded exact copy too.
        digest = hashlib.sha256(image.tobytes()).hexdigest()
        if digest in hash_splits and hash_splits[digest] != split:
            raise ValueError("image_duplicate_across_splits")
        hash_splits[digest] = split
        q = quality(image)
        if not q["passed"]:
            raise ValueError(f"training_image_quality_failure: {row['path']}: {q['reasons']}")
        prepared.append((row, LABELS.index(label), features(image)))
    for split in ("train", "validation", "test"):
        if split in excluded_splits:
            continue
        if {label for row, label, _ in prepared if row["split"] == split} != {0, 1, 2}:
            raise ValueError(f"all_classes_required_in_{split}")
    return prepared


def arrays(prepared, split):
    selected = [(label, vector) for row, label, vector in prepared if row["split"] == split]
    return np.stack([v for _, v in selected]), np.array([y for y, _ in selected], dtype=np.int64)


def augmented_training_arrays(prepared, manifest, preprocessing="none"):
    """Train only: original + 4 mild geometry variants, retaining the full ROI.

    No vertical flip, 90-degree rotation, synthetic ridges, or test augmentation.
    """
    x, y = arrays(prepared, "train")
    vectors, labels = list(x), list(y)
    base = Path(manifest).resolve().parent
    for row, label, _ in prepared:
        if row["split"] != "train":
            continue
        image = load_image(base / row["path"], preprocessing=preprocessing)
        raw = Image.fromarray(np.uint8(np.clip(image * 255, 0, 255)))
        for angle, dx, dy in [(-8, -3, 0), (-4, 0, 3), (4, 0, -3), (8, 3, 0)]:
            padded = Image.new("L", (144, 144), 255)
            padded.paste(raw, (8 + dx, 8 + dy))
            varied = padded.rotate(angle, resample=Image.Resampling.BILINEAR,
                                  expand=True, fillcolor=255).resize((128, 128), Image.Resampling.BILINEAR)
            vectors.append(features(np.asarray(varied, dtype=np.float32) / 255))
            labels.append(label)
    return np.stack(vectors), np.asarray(labels, dtype=np.int64)
