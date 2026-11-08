"""Image checks, orientation features, and a learned linear softmax model.

NumPy/Pillow only. This is not a biometric recognition or liveness model.
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

LABELS = ("arch", "loop", "whorl")
VERSION = "orientation-softmax-v1"
SIZE = 128


def map_label(value):
    aliases = {
        "arch": "arch", "plain_arch": "arch", "tented_arch": "arch",
        "loop": "loop", "left_loop": "loop", "right_loop": "loop",
        "radial_loop": "loop", "ulnar_loop": "loop", "whorl": "whorl",
        "plain_whorl": "whorl", "central_pocket_whorl": "whorl",
        "double_loop_whorl": "whorl", "accidental_whorl": "whorl",
    }
    key = value.strip().lower().replace(" ", "_").replace("-", "_")
    if key not in aliases:
        raise ValueError(f"Unmapped/ambiguous label: {value!r}")
    return aliases[key]


def load_image(path, preprocessing="none"):
    if preprocessing not in {"none", "autocontrast-1pct"}:
        raise ValueError("unsupported_preprocessing")
    path = Path(path)
    if path.stat().st_size > 10 * 1024 * 1024:
        raise ValueError("image_too_large_bytes")
    try:
        with Image.open(path) as im:
            if im.format not in {"PNG", "JPEG"}:
                raise ValueError("unsupported_format_use_png_or_jpeg")
            if max(im.size) > 8192 or min(im.size) < 64:
                raise ValueError("unsupported_dimensions")
            if getattr(im, "n_frames", 1) != 1:
                raise ValueError("multiple_frames_not_supported")
            im = ImageOps.exif_transpose(im)
            # Input must already be the central ROI: do not silently crop away core.
            if max(im.size) / min(im.size) > 1.5:
                raise ValueError("roi_aspect_ratio_over_1_5")
            im = im.convert("L")
            if preprocessing == "autocontrast-1pct":
                im = ImageOps.autocontrast(im, cutoff=1)
            im = im.resize((SIZE, SIZE), Image.Resampling.BILINEAR)
            return np.asarray(im, dtype=np.float32) / 255.0
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("invalid_image") from exc


def quality(image):
    if image.shape != (SIZE, SIZE) or not np.isfinite(image).all():
        raise ValueError("invalid_image_array")
    gy, gx = np.gradient(image)
    contrast = float(image.std())
    gradient = float(np.sqrt(np.mean(gx * gx + gy * gy)))
    clipped = float(np.mean((image < 0.01) | (image > 0.99)))
    reasons = []
    if contrast < 0.045:
        reasons.append("low_contrast")
    if gradient < 0.01:
        reasons.append("insufficient_visible_texture")
    if clipped > 0.98:
        reasons.append("mostly_clipped")
    return {"passed": not reasons, "reasons": reasons, "contrast": contrast,
            "gradient_rms": gradient, "clipped_fraction": clipped,
            "note": "Provisional image checks; not proof of a fingerprint or liveness."}


def features(image):
    """16x16 grid of normalized gradient structure tensor components.

    Gradient polarity is removed. A doubled-angle encoding respects 180-degree
    ridge direction periodicity. No density/minutiae/identity output is exposed.
    """
    gy, gx = np.gradient(image)
    def pool(a):
        return a.reshape(16, 8, 16, 8).mean(axis=(1, 3))
    jxx, jyy, jxy = pool(gx * gx), pool(gy * gy), pool(gx * gy)
    denom = jxx + jyy + 1e-6
    return np.stack(((jxx - jyy) / denom, 2 * jxy / denom), axis=-1).ravel().astype(np.float32)


def softmax(logits):
    z = logits - logits.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def fit(x, y, xv, yv, *, epochs=300, learning_rate=0.08, l2=0.002, seed=42, class_balanced=False):
    """Full-batch gradient optimization; validation selects the epoch, never test."""
    if len(set(y.tolist())) != 3:
        raise ValueError("training_requires_all_three_classes")
    rng = np.random.default_rng(seed)
    mean, scale = x.mean(0), np.maximum(x.std(0), 0.15)
    z, zv = (x - mean) / scale, (xv - mean) / scale
    w = rng.normal(0, 0.002, (x.shape[1], 3)).astype(np.float32)
    b = np.zeros(3, np.float32)
    target = np.eye(3, dtype=np.float32)[y]
    class_weights = len(y) / (3 * np.bincount(y, minlength=3)) if class_balanced else np.ones(3)
    best, best_loss, history = None, float("inf"), []
    for epoch in range(1, epochs + 1):
        p = softmax(z @ w + b)
        grad = (p - target) * class_weights[y, None] / len(y)
        w -= learning_rate * (z.T @ grad + l2 * w)
        b -= learning_rate * grad.sum(0)
        pv = softmax(zv @ w + b)
        loss = float(-np.log(np.clip(pv[np.arange(len(yv)), yv], 1e-9, 1)).mean())
        if loss < best_loss:
            best_loss, best = loss, (w.copy(), b.copy(), epoch)
        if epoch == 1 or epoch % 25 == 0 or epoch == epochs:
            history.append({"epoch": epoch, "validation_cross_entropy": loss})
    w, b, best_epoch = best
    centers = np.stack([z[y == k].mean(0) for k in range(3)])
    # Provisional rejection thresholds use validation only; not real-domain OOD calibration.
    pv = softmax(zv @ w + b)
    correct_scores = pv.max(1)[pv.argmax(1) == yv]
    threshold = float(max(0.55, np.quantile(correct_scores, 0.05))) if len(correct_scores) else 0.99
    radii = []
    for k in range(3):
        d = np.sqrt(np.mean((zv[yv == k] - centers[k]) ** 2, axis=1))
        if not len(d):
            raise ValueError("validation_requires_all_three_classes")
        radii.append(float(max(np.quantile(d, 0.99) * 1.1, 0.01)))
    return {"mean": mean, "scale": scale, "weights": w, "bias": b,
            "centers": centers, "radii": np.array(radii), "threshold": np.array(threshold)}, {
                "best_epoch": best_epoch, "validation_loss": best_loss, "history": history,
                "class_weights": class_weights.tolist(), "class_balanced": class_balanced}


def scores(model, x):
    return softmax(((x - model["mean"]) / model["scale"]) @ model["weights"] + model["bias"])


def save_model(path, model, metadata):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **model, metadata=np.array(json.dumps(metadata)))


def read_model(path):
    with np.load(path, allow_pickle=False) as data:
        metadata = json.loads(str(data["metadata"].item()))
        model = {k: data[k].copy() for k in (
            "mean", "scale", "weights", "bias", "centers", "radii", "threshold")}
    if metadata.get("labels") != list(LABELS) or metadata.get("version") != VERSION:
        raise ValueError("unsupported_model_contract")
    expected = {"mean": (512,), "scale": (512,), "weights": (512, 3),
                "bias": (3,), "centers": (3, 512), "radii": (3,), "threshold": ()}
    if any(model[k].shape != shape or not np.isfinite(model[k]).all() for k, shape in expected.items()):
        raise ValueError("invalid_model_arrays")
    if (model["scale"] <= 0).any() or (model["radii"] <= 0).any() or not 0 <= float(model["threshold"]) <= 1:
        raise ValueError("invalid_model_bounds")
    return model, metadata


def predict(model, metadata, image, *, source="real", allow_unvalidated_real=False):
    if source not in {"real", "synthetic"}:
        raise ValueError("source_must_be_real_or_synthetic")
    q = quality(image)
    result = {"status": "quality_failure", "label": None, "candidate_label": None,
              "scores": None, "quality": q, "training_domain": metadata["training_domain"],
              "source": source, "version": VERSION,
              "preprocessing": metadata.get("preprocessing", "none"),
              "annotation_status": metadata.get("annotation_status", "see-model-card"),
              "warning": ("Synthetic-only baseline. " if metadata["training_domain"] == "synthetic-only" else
                          "Provisional external-data model; labels unvalidated. ") +
                         "Scores are not calibrated correctness probabilities. No real-phone validation."}
    if not q["passed"]:
        return result
    x = features(image)
    p = scores(model, x[None])[0]
    k = int(p.argmax())
    z = (x - model["mean"]) / model["scale"]
    distance = float(np.sqrt(np.mean((z - model["centers"][k]) ** 2)))
    result.update(candidate_label=LABELS[k], scores=dict(zip(LABELS, map(float, p))),
                  rejection_distance=distance, score_threshold=float(model["threshold"]))
    if source == "real" and not allow_unvalidated_real:
        # Never promote an unvalidated real input to an accepted classification.
        result.update(status="unsupported_domain", reason="real_phone_validation_not_completed")
    elif float(p[k]) < float(model["threshold"]) or distance > float(model["radii"][k]):
        result.update(status="unknown", reason="provisional_score_or_distance_rejection")
    else:
        result.update(status="experimental" if source == "real" else "ok", label=LABELS[k])
    if source == "real" and allow_unvalidated_real:
        result["experimental_override"] = True
        result["warning"] = "EXPERIMENTAL REAL INPUT: not validated on phone photographs. Do not present as reliable classification. Scores are uncalibrated."
    return result
