import csv
from pathlib import Path
import tempfile
import unittest
import zipfile

from PIL import Image

from fingerprint_model.annotation import FIELDS, export, intake, read_rows, safe_zip_entries
from fingerprint_model.synthetic import generate


class AnnotationTests(unittest.TestCase):
    def test_zip_traversal_and_expansion_limits(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.zip"
            for name in ("../outside.png", "C:/outside.png", "..\\outside.png"):
                with zipfile.ZipFile(path, "w") as archive:
                    archive.writestr(name, b"bad")
                with zipfile.ZipFile(path) as archive:
                    with self.assertRaisesRegex(ValueError, "unsafe_zip_path"):
                        safe_zip_entries(archive)
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("huge.png", bytes(21 * 1024 * 1024))
            with zipfile.ZipFile(path) as archive:
                with self.assertRaisesRegex(ValueError, "expansion_limit"):
                    safe_zip_entries(archive)

    def test_import_preserves_entire_image_and_leaves_labels_empty(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            source = base / "source"
            source.mkdir()
            image = Image.new("RGB", (180, 100), "gray")
            exif = image.getexif()
            exif[274] = 6
            image.save(source / "rotated.jpg", exif=exif)
            (source / "invalid.png").write_bytes(b"not image")
            result = intake(source, base / "review", "test-fixture", "unit-test")
            self.assertEqual((result["imported"], result["failed"]), (1, 1))
            row = read_rows(base / "review/annotations.csv")[0]
            self.assertEqual(row["label"], "")
            self.assertEqual(row["group_id"], "")
            self.assertEqual(row["review_status"], "pending")
            self.assertEqual((base / "review" / row["original_path"]).read_bytes(), (source / "rotated.jpg").read_bytes())
            with Image.open(base / "review" / row["path"]) as converted:
                self.assertEqual(converted.size, (100, 180))
                self.assertFalse(converted.getexif())

    def test_review_export_exclusions_agreement_and_group_safety(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            generate(base / "fixtures", identities=12, impressions=1, seed=17)
            intake(base / "fixtures/images", base / "review", "test-fixture", "synthetic test only")
            file = base / "review/annotations.csv"
            rows = read_rows(file)
            # Test fixtures only: deliberately supply human-like fields to exercise the contract.
            for index, row in enumerate(rows):
                label = ("arch", "loop", "whorl")[index % 3]
                row.update(label=label, second_label=label, reviewer="r1", second_reviewer="r2",
                           evidence="fixture", second_evidence="fixture", group_id=f"g{index}",
                           split=("train", "validation", "test")[(index // 3) % 3],
                           review_status="agreed", quality_status="pass", pattern_coverage="sufficient")
            def save():
                with file.open("w", encoding="utf-8", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=FIELDS)
                    writer.writeheader()
                    writer.writerows(rows)
            rows[-1]["review_status"] = "pending"
            save()
            result = export(file)
            self.assertEqual(result["selected"], len(rows) - 1)
            self.assertEqual(result["excluded"], [rows[-1]["image_id"]])
            rows[0]["second_label"] = "unknown"
            save()
            with self.assertRaises(ValueError):
                export(file, "wrong.csv")
            rows[0]["second_label"] = rows[0]["label"]
            rows[0]["second_reviewer"] = "r1"
            save()
            with self.assertRaisesRegex(ValueError, "distinct_reviewers"):
                export(file, "same.csv")
            rows[0]["second_reviewer"] = "r2"
            rows[3]["group_id"] = rows[0]["group_id"]
            save()
            with self.assertRaisesRegex(ValueError, "group_leakage"):
                export(file, "leak.csv")
            rows[3]["group_id"] = "g3"
            rows[0]["review_status"] = "provisional"
            rows[0]["pattern_coverage"] = "morphology_only"
            rows[0]["second_reviewer"] = ""
            rows[0]["second_label"] = ""
            rows[0]["second_evidence"] = ""
            save()
            provisional = export(file, "provisional.csv", allow_provisional=True)
            self.assertEqual(provisional["policy"], "provisional-experiment")
            self.assertIn("SINGLE-REVIEW-PROVISIONAL", (file.parent / "provisional.csv").read_text(encoding="utf-8-sig"))
            self.assertIn("MORPHOLOGY-ONLY", (file.parent / "provisional.csv").read_text(encoding="utf-8-sig"))
            rows[1]["sha256"] = "changed"
            save()
            with self.assertRaisesRegex(ValueError, "changed_since_intake"):
                export(file, "changed.csv", allow_provisional=True)


if __name__ == "__main__":
    unittest.main()
