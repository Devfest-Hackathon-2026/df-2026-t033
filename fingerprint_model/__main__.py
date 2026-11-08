import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import platform
import sys

import numpy as np
import PIL

from .core import LABELS, VERSION, fit, load_image, predict, read_model, save_model, scores
from .data import arrays, read_manifest, augmented_training_arrays
from .synthetic import generate


def metrics(y, p):
    pred = p.argmax(1)
    cm = np.zeros((3, 3), dtype=int)
    for actual, estimated in zip(y, pred):
        cm[actual, estimated] += 1
    recalls = np.diag(cm) / np.maximum(cm.sum(1), 1)
    precision = np.diag(cm) / np.maximum(cm.sum(0), 1)
    f1 = 2 * recalls * precision / np.maximum(recalls + precision, 1e-12)
    return {"count": len(y), "accuracy": float(np.mean(pred == y)),
            "macro_f1": float(f1.mean()), "recall": dict(zip(LABELS, recalls.tolist())),
            "confusion_matrix_rows_true_columns_predicted": cm.tolist()}


def train(args):
    from .audit import verify_lock
    output = Path(args.output)
    if output.exists():
        raise ValueError("output_directory_already_exists_use_a_new_run_name")
    partition_lock = verify_lock(args.manifest, args.partition_lock) if args.partition_lock else None
    prepared = read_manifest(args.manifest, preprocessing=args.preprocessing)
    if any(r["source"] == "real" for r, _, _ in prepared) and partition_lock is None:
        raise ValueError("real_training_requires_partition_lock_use_fingerprint_model.audit_lock_first")
    x, y = arrays(prepared, "train")
    if args.augment_train:
        x, y = augmented_training_arrays(prepared, args.manifest, args.preprocessing)
    xv, yv = arrays(prepared, "validation")
    xt, yt = arrays(prepared, "test")
    model, optimization = fit(x, y, xv, yv, epochs=args.epochs, seed=args.seed, class_balanced=args.class_balanced)
    domain = "synthetic-only" if all(r["source"] == "synthetic" for r, _, _ in prepared) else "external-unvalidated"
    metadata = {"labels": list(LABELS), "version": VERSION, "training_domain": domain,
                "preprocessing": args.preprocessing,
                "training_augmentation": "mild-geometry-v1" if args.augment_train else "none",
                "partition_lock_manifest_sha256": partition_lock["manifest_sha256"] if partition_lock else None,
                "evaluation_status": partition_lock["evaluation_status"] if partition_lock else "see-experiment-protocol",
                "annotation_status": "single-review-provisional" if any("SINGLE-REVIEW-PROVISIONAL" in r["provenance"] for r, _, _ in prepared) else "see-manifest-provenance",
                "seed": args.seed, "real_phone_validated": False,
                "manifest_sha256": hashlib.sha256(Path(args.manifest).read_bytes()).hexdigest()}
    output.mkdir(parents=True)
    save_model(output / "model.npz", model, metadata)
    # Test split is touched for final evaluation only, after validation selection.
    ptest = scores(model, xt)
    zt = (xt - model["mean"]) / model["scale"]
    pred = ptest.argmax(1)
    d = np.sqrt(np.mean((zt - model["centers"][pred]) ** 2, axis=1))
    accepted = (ptest.max(1) >= model["threshold"]) & (d <= model["radii"][pred])
    report = {"metadata": metadata, "environment": {"python": platform.python_version(),
              "numpy": np.__version__, "pillow": PIL.__version__}, "optimization": optimization,
              "split_image_counts": dict(Counter(r["split"] for r, _, _ in prepared)),
              "training_vectors_including_augmentation": len(y),
              "split_group_counts": {s: len({r["group_id"] for r, _, _ in prepared if r["split"] == s})
                                     for s in ("train", "validation", "test")},
              "group_overlap": False, "test": metrics(yt, ptest),
              "rejection": {"threshold": float(model["threshold"]), "accepted": int(accepted.sum()),
                            "unknown": int((~accepted).sum()), "coverage": float(accepted.mean()),
                            "accuracy_among_accepted": float(np.mean(pred[accepted] == yt[accepted])) if accepted.any() else None,
                            "calibration_domain": "validation split only; not real-phone calibrated"},
              "limitations": ["No real-phone validation. Scores are not calibrated correctness probabilities.",
                              "Unknown rejection does not reliably detect out-of-distribution images."] + (
                              ["Procedural motifs only; not anatomically validated fingerprints."] if domain == "synthetic-only" else
                              ["External scan labels may be single-AI provisional morphology candidates, not verified ground truth.",
                               "Very small selected evaluation sets do not establish general accuracy."])}
    (output / "metrics.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"model": str(output / "model.npz"), "domain": domain, "test": report["test"],
                      "rejection": report["rejection"]}, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Experimental arch/loop/whorl classifier; real inputs are unvalidated")
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate")
    gen.add_argument("--output", required=True)
    gen.add_argument("--identities", type=int, default=120, help="Base motifs PER CLASS")
    gen.add_argument("--impressions", type=int, default=4)
    gen.add_argument("--seed", type=int, default=20261108)
    tr = sub.add_parser("train")
    tr.add_argument("--manifest", required=True)
    tr.add_argument("--output", required=True)
    tr.add_argument("--epochs", type=int, default=300)
    tr.add_argument("--seed", type=int, default=42)
    tr.add_argument("--preprocessing", choices=["none", "autocontrast-1pct"], default="none")
    tr.add_argument("--augment-train", action="store_true")
    tr.add_argument("--class-balanced", action="store_true")
    tr.add_argument("--partition-lock", help="Required for real-data training; verifies manifest, groups, splits, labels, and image bytes")
    pr = sub.add_parser("predict")
    pr.add_argument("--model", required=True)
    pr.add_argument("--image", required=True, help="Already cropped central ROI, PNG/JPEG")
    pr.add_argument("--source", choices=["real", "synthetic"], default="real")
    pr.add_argument("--allow-unvalidated-real", action="store_true", help="Explicit local experiment only; output remains experimental/unknown")
    args = parser.parse_args()
    try:
        if args.command == "generate":
            print(generate(args.output, args.identities, args.impressions, args.seed))
        elif args.command == "train":
            if args.epochs < 1:
                raise ValueError("epochs_must_be_positive")
            train(args)
        else:
            model, metadata = read_model(args.model)
            print(json.dumps(predict(model, metadata, load_image(args.image, preprocessing=metadata.get("preprocessing", "none")), source=args.source,
                                     allow_unvalidated_real=args.allow_unvalidated_real), indent=2))
    except (ValueError, OSError, KeyError) as exc:
        print(json.dumps({"status": "error", "reason": str(exc)}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
