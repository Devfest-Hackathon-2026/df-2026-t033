import csv
import json
from pathlib import Path
import tempfile
import unittest

from fingerprint_model.audit import create_lock, verify_lock, plan_nested_folds, cross_validate
from fingerprint_model.data import read_manifest
from fingerprint_model.synthetic import generate


class AuditTests(unittest.TestCase):
    def test_lock_rejects_manifest_or_image_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generate(root/'data', identities=12, impressions=1, seed=8)
            manifest = root/'data/manifest.csv'; lock = root/'lock.json'
            create_lock(manifest,lock); verify_lock(manifest,lock)
            original = manifest.read_bytes()
            manifest.write_bytes(original + b'\n')
            with self.assertRaisesRegex(ValueError,'changed_since_lock'): verify_lock(manifest,lock)
            manifest.write_bytes(original)
            with manifest.open(encoding='utf-8-sig') as f:
                row = next(csv.DictReader(f))
            file = manifest.parent / row['path']; file.write_bytes(file.read_bytes()+b'changed')
            with self.assertRaisesRegex(ValueError,'changed_since_lock'): verify_lock(manifest,lock)
            with self.assertRaisesRegex(ValueError,'already_exists'): create_lock(manifest,lock)

    def test_excluded_test_images_not_decoded_and_folds_are_disjoint(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            generate(root/'data', identities=12, impressions=1, seed=9)
            manifest=root/'data/manifest.csv'
            with manifest.open(encoding='utf-8-sig') as f: rows=list(csv.DictReader(f))
            for row in rows:
                if row['split']=='test': (manifest.parent/row['path']).write_bytes(b'not an image')
            records=read_manifest(manifest,excluded_splits=('test',))
            plans=plan_nested_folds(records,folds=3,seed=10)
            outer=[]
            for plan in plans:
                train,val,test=map(set,[plan['train'],plan['validation'],plan['outer']])
                self.assertFalse(train&val or train&test or val&test)
                for groups in (train,val,test):
                    self.assertEqual({label for row,label,_ in records if row['group_id'] in groups},{0,1,2})
                outer.extend(test)
            self.assertEqual(len(outer),len(set(outer)))
            self.assertEqual(set(outer),{row['group_id'] for row,_,_ in records})

    def test_nested_cv_smoke_excludes_original_test_partition(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            generate(root/'data', identities=12, impressions=1, seed=11)
            manifest=root/'data/manifest.csv'; lock=root/'lock.json'
            create_lock(manifest,lock)
            report=cross_validate(manifest,lock,root/'cv',epochs=2,folds=3,seed=10)
            self.assertEqual(report['development_rows'],report['pooled_outer']['count'])
            self.assertGreater(report['excluded_original_test_rows'],0)
            self.assertEqual(len(report['folds']),3)
            self.assertTrue((root/'cv/fold-plan.json').exists())


if __name__=='__main__': unittest.main()
