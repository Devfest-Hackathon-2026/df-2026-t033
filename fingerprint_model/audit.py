"""Prospective partition lock and nested group CV on development rows only."""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path
import sys

import numpy as np

from .core import fit, scores
from .data import read_manifest, arrays, augmented_training_arrays


def partition_snapshot(manifest):
    manifest = Path(manifest).resolve()
    with manifest.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    snapshots = []
    groups = {}
    for row in rows:
        if not all(row.get(k) for k in ["path", "label", "group_id", "split", "source", "license", "provenance"]):
            raise ValueError("invalid_manifest_for_lock")
        file = (manifest.parent / row["path"]).resolve()
        if not file.is_relative_to(manifest.parent):
            raise ValueError("image_path_outside_manifest")
        group, split = row["group_id"], row["split"]
        if split not in {"train", "validation", "test"}:
            raise ValueError("invalid_split")
        if group in groups and groups[group] != split:
            raise ValueError("group_leakage")
        groups[group] = split
        snapshots.append({**row, "file_sha256": hashlib.sha256(file.read_bytes()).hexdigest()})
    if not snapshots:
        raise ValueError("empty_manifest")
    return {"manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(), "rows": snapshots}


def create_lock(manifest, output):
    output = Path(output)
    if output.exists():
        raise ValueError("lock_already_exists_do_not_overwrite")
    snapshot = partition_snapshot(manifest)
    lock = {"format": "fingerprint-partition-lock-v1", "created_utc": datetime.now(timezone.utc).isoformat(),
            "evaluation_status": "development-only; previously inspected evaluation is not a final holdout",
            "historical_claim": "Prospective integrity check only; cannot prove past chronology or label correctness.",
            **snapshot}
    output.write_text(json.dumps(lock, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"lock": str(output), "rows": len(snapshot["rows"]), "evaluation_status": lock["evaluation_status"]}


def verify_lock(manifest, lock_path):
    lock = json.loads(Path(lock_path).read_text(encoding="utf-8"))
    if lock.get("format") != "fingerprint-partition-lock-v1":
        raise ValueError("unsupported_partition_lock")
    actual = partition_snapshot(manifest)
    if any(lock.get(k) != actual[k] for k in ("manifest_sha256", "rows")):
        raise ValueError("partition_or_image_changed_since_lock")
    return lock


def labels_for(records, groups):
    return {label for row, label, _ in records if row["group_id"] in groups}


def plan_nested_folds(records, folds=3, seed=20261108):
    if folds < 2:
        raise ValueError("at_least_two_folds_required")
    groups = sorted({row["group_id"] for row, _, _ in records})
    if len(groups) < folds:
        raise ValueError("not_enough_groups")
    rng = np.random.default_rng(seed)
    for attempt in range(1000):
        order = list(rng.permutation(groups))
        outer = [set(order[i::folds]) for i in range(folds)]
        if any(labels_for(records, g) != {0, 1, 2} for g in outer):
            continue
        plans = []
        for held in outer:
            remaining = set(groups) - held
            inner = None
            # Choose a small validation by labels/groups only, never feature scores.
            choices = list(rng.permutation(sorted(remaining)))
            for count in range(3, min(6, len(choices))):
                for selected in itertools.combinations(choices, count):
                    val = set(selected)
                    if labels_for(records, val) == {0, 1, 2} and labels_for(records, remaining - val) == {0, 1, 2}:
                        inner = val
                        break
                if inner is not None:
                    break
            if inner is None:
                break
            plans.append({"train": sorted(remaining - inner), "validation": sorted(inner), "outer": sorted(held)})
        if len(plans) == folds:
            return plans
    raise ValueError("cannot_form_nested_group_folds_with_all_classes")


def cross_validate(manifest, lock_path, output, epochs=300, folds=3, seed=20261108):
    from .__main__ import metrics
    output = Path(output)
    if output.exists():
        raise ValueError("cv_output_already_exists")
    if epochs < 1:
        raise ValueError("epochs_must_be_positive")
    lock = verify_lock(manifest, lock_path)
    # Crucially, old test rows are not decoded or featurized in this path.
    records = read_manifest(manifest, preprocessing="autocontrast-1pct", excluded_splits=("test",))
    plans = plan_nested_folds(records, folds=folds, seed=seed)
    output.mkdir(parents=True)
    # Persist the full plan BEFORE the first fit; this is not a historical v2 lock.
    (output / "fold-plan.json").write_text(json.dumps({"seed": seed, "plans": plans,
        "manifest_sha256": lock["manifest_sha256"]}, indent=2), encoding="utf-8")
    reports, all_y, all_p, all_baseline = [], [], [], []
    for number, plan in enumerate(plans):
        mapped = []
        for row, label, vector in records:
            group = row["group_id"]
            split = "train" if group in plan["train"] else "validation" if group in plan["validation"] else "test"
            mapped.append(({**row, "split": split}, label, vector))
        x, y = augmented_training_arrays(mapped, manifest, "autocontrast-1pct")
        xv, yv = arrays(mapped, "validation")
        xt, yt = arrays(mapped, "test")
        model, optimization = fit(x, y, xv, yv, epochs=epochs, seed=seed + number, class_balanced=True)
        p = scores(model, xt)
        distances = np.sqrt(np.mean((((xt - model["mean"]) / model["scale"]) - model["centers"][p.argmax(1)]) ** 2, axis=1))
        accepted = (p.max(1) >= model["threshold"]) & (distances <= model["radii"][p.argmax(1)])
        baseline = np.zeros_like(p)
        baseline[:, int(np.bincount(y, minlength=3).argmax())] = 1
        reports.append({"fold": number + 1, "counts": dict(Counter(r["split"] for r, _, _ in mapped)),
                        "group_counts": {s: len(g) for s, g in plan.items()}, "best_epoch": optimization["best_epoch"],
                        "outer": metrics(yt, p), "majority_baseline": metrics(yt, baseline),
                        "accepted": int(accepted.sum()), "unknown": int((~accepted).sum()),
                        "accepted_correct": int(((p.argmax(1) == yt) & accepted).sum())})
        all_y.extend(yt.tolist()); all_p.extend(p.tolist()); all_baseline.extend(baseline.tolist())
    report = {"purpose": "Nested group CV on development rows only; not final generalization estimate",
              "manifest_sha256": lock["manifest_sha256"], "excluded_original_test_rows": sum(r["split"] == "test" for r in lock["rows"]),
              "development_rows": len(records), "development_groups": len({r["group_id"] for r, _, _ in records}),
              "seed": seed, "folds": reports, "pooled_outer": metrics(np.array(all_y), np.array(all_p)),
              "pooled_majority_baseline": metrics(np.array(all_y), np.array(all_baseline)),
              "limitations": ["Provisional single-AI labels, selected images, very small minority class.",
                              "No smartphone final holdout; former test rows excluded from this CV.",
                              "Group identity depends on source folders and duplicate audit; approximate duplicates may remain."]}
    (output / "metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    lock = sub.add_parser("lock")
    lock.add_argument("--manifest", required=True); lock.add_argument("--output", required=True)
    check = sub.add_parser("verify")
    check.add_argument("--manifest", required=True); check.add_argument("--lock", required=True)
    cv = sub.add_parser("cv")
    cv.add_argument("--manifest", required=True); cv.add_argument("--lock", required=True); cv.add_argument("--output", required=True)
    cv.add_argument("--epochs", type=int, default=300); cv.add_argument("--folds", type=int, default=3); cv.add_argument("--seed", type=int, default=20261108)
    args = parser.parse_args()
    try:
        if args.command == "lock": result = create_lock(args.manifest, args.output)
        elif args.command == "verify":
            verify_lock(args.manifest, args.lock); result = {"status": "lock_matches"}
        else: result = cross_validate(args.manifest, args.lock, args.output, args.epochs, args.folds, args.seed)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError) as exc:
        print(json.dumps({"status": "error", "reason": str(exc)}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
