import csv
import tempfile
from pathlib import Path
import unittest

import numpy as np
from PIL import Image

from fingerprint_model.core import LABELS, VERSION, fit, load_image, map_label, predict, read_model, save_model
from fingerprint_model.data import arrays, read_manifest
from fingerprint_model.synthetic import generate


class PipelineTests(unittest.TestCase):
    def test_label_mapping_and_ambiguity(self):
        self.assertEqual(map_label("Tented Arch"), "arch")
        self.assertEqual(map_label("right-loop"), "loop")
        self.assertEqual(map_label("double loop whorl"), "whorl")
        for label in ("double_loop", "peacock-eye", "unknown", "whorls-loops-arch-"):
            with self.assertRaises(ValueError):
                map_label(label)

    def test_invalid_images(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root) / "invalid.png"
            p.write_text("not an image")
            with self.assertRaises(ValueError):
                load_image(p)
            Image.new("L", (32, 32)).save(p)
            with self.assertRaises(ValueError):
                load_image(p)

    def test_training_roundtrip_quality_and_domain(self):
        with tempfile.TemporaryDirectory() as root:
            manifest = generate(Path(root) / "dataset", identities=12, impressions=2, seed=31)
            records = read_manifest(manifest)
            x, y = arrays(records, "train")
            xv, yv = arrays(records, "validation")
            model, _ = fit(x, y, xv, yv, epochs=15)
            metadata = {"version": VERSION, "labels": list(LABELS), "training_domain": "synthetic-only"}
            checkpoint = Path(root) / "model.npz"
            save_model(checkpoint, model, metadata)
            loaded, meta = read_model(checkpoint)
            test_row = next(r for r, _, _ in records if r["split"] == "test")
            image = load_image(manifest.parent / test_row["path"])
            before = predict(model, metadata, image)
            after = predict(loaded, meta, image)
            self.assertEqual(before, after)
            self.assertEqual(after["status"], "unsupported_domain")
            self.assertIsNone(after["label"])
            override = predict(loaded, meta, image, allow_unvalidated_real=True)
            self.assertIn(override["status"], {"experimental", "unknown"})
            self.assertTrue(override["experimental_override"])
            self.assertAlmostEqual(sum(after["scores"].values()), 1, places=6)
            self.assertEqual(predict(loaded, meta, np.full((128, 128), .5, np.float32))["status"], "quality_failure")

    def test_group_leakage_and_exact_duplicate(self):
        with tempfile.TemporaryDirectory() as root:
            manifest = generate(Path(root) / "dataset", identities=10, impressions=2)
            with manifest.open(newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            original = [dict(r) for r in rows]
            # Move one impression away from its base motif's split.
            rows[1]["split"] = "test"
            self._write(manifest, rows)
            with self.assertRaisesRegex(ValueError, "group_leakage"):
                read_manifest(manifest)
            rows = original
            source = manifest.parent / rows[0]["path"]
            target_row = next(r for r in rows if r["split"] == "test")
            target = manifest.parent / target_row["path"]
            target.write_bytes(source.read_bytes())
            self._write(manifest, rows)
            with self.assertRaisesRegex(ValueError, "image_duplicate_across_splits"):
                read_manifest(manifest)

    @staticmethod
    def _write(path, rows):
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
