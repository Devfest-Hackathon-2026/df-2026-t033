from pathlib import Path
import tempfile
import unittest
from PIL import Image
import numpy as np
from fingerprint_model.data import duplicate_connected_groups, augmented_training_arrays
from fingerprint_model.core import load_image


class DuplicateGroupTests(unittest.TestCase):
    def test_augmentation_never_reads_validation_or_test_images(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pixels = np.tile(np.arange(128, dtype=np.uint8), (128, 1))
            Image.fromarray(pixels).save(root / 'train.png')
            prepared = [({'path':'train.png','split':'train'},0,np.zeros(512)),
                        ({'path':'missing-val.png','split':'validation'},1,np.zeros(512)),
                        ({'path':'missing-test.png','split':'test'},2,np.zeros(512))]
            x,y = augmented_training_arrays(prepared,root/'manifest.csv')
            self.assertEqual(x.shape,(5,512))
            self.assertEqual(y.tolist(),[0]*5)
            self.assertTrue(np.isfinite(x).all())

    def test_declared_contrast_preprocessing_preserves_shape_and_is_deterministic(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / 'low.png'
            pixels = np.tile(np.linspace(210, 230, 128, dtype=np.uint8), (128, 1))
            Image.fromarray(pixels).save(file)
            raw = load_image(file)
            enhanced = load_image(file, preprocessing='autocontrast-1pct')
            self.assertEqual(enhanced.shape, raw.shape)
            self.assertGreater(float(enhanced.std()), float(raw.std()) * 5)
            np.testing.assert_array_equal(enhanced, load_image(file, preprocessing='autocontrast-1pct'))
            with self.assertRaisesRegex(ValueError, 'unsupported_preprocessing'):
                load_image(file, preprocessing='unknown')

    def test_transitive_pixel_duplicates_join_families(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            Image.new('L', (80, 80), 40).save(root / 'a.png')
            Image.new('L', (80, 80), 80).save(root / 'b.png')
            Image.new('L', (80, 80), 120).save(root / 'c.png')
            mapping, stats = duplicate_connected_groups([(root/'a.png','family1'),
                (root/'a.png','family2'), (root/'b.png','family2'), (root/'b.png','family3'),
                (root/'c.png','family4')])
            self.assertEqual(mapping['family1'], mapping['family3'])
            self.assertNotEqual(mapping['family1'], mapping['family4'])
            self.assertEqual(stats['unique_decoded_images'], 3)
            self.assertEqual(stats['connected_groups'], 2)
