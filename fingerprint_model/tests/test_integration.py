import hashlib
import io
import unittest
from pathlib import Path
from PIL import Image
from fingerprint_model.integration import FingerprintClassifier, ASSET


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.classifier=FingerprintClassifier()
        cls.fixture=ASSET.parents[1]/'synthetic-demo.png'

    def test_bytes_path_and_bundled_checksum(self):
        a=self.classifier.predict(self.fixture,domain='scan')
        b=self.classifier.predict(self.fixture.read_bytes(),domain='scan')
        self.assertEqual(a,b)
        self.assertEqual(a['model_sha256'],hashlib.sha256(ASSET.read_bytes()).hexdigest())
        self.assertIn(a['candidate'],('arch','loop','whorl',None))
        self.assertTrue(a['needs_review']);self.assertTrue(a['experimental'])
        self.assertIsNone(a['verified_label'])

    def test_invalid_inputs_have_stable_contract(self):
        for value,kwargs in [(b'not image',{}),(b'x'*(20*1024*1024+1),{}),
                             (self.fixture,{'roi':[0,0,10.5,20]}),
                             (self.fixture,{'roi':[0,0,900,900]}),
                             (self.fixture,{'domain':'other'}),(42,{})]:
            r=self.classifier.predict(value,**kwargs)
            self.assertEqual(r['decision'],'error');self.assertIsNone(r['candidate'])
            self.assertIsInstance(r['quality'],dict);self.assertTrue(r['reasons'])
            self.assertNotIn(str(self.fixture),str(r))

    def test_format_frame_dimension_checks(self):
        for image,fmt in [(Image.new('RGB',(32,32)),'PNG'),(Image.new('RGB',(100,100)),'BMP')]:
            b=io.BytesIO();image.save(b,format=fmt)
            self.assertEqual(self.classifier.predict(b.getvalue())['decision'],'error')
        b=io.BytesIO();Image.new('RGB',(100,100)).save(b,format='PNG',save_all=True,
            append_images=[Image.new('RGB',(100,100),'white')])
        self.assertEqual(self.classifier.predict(b.getvalue())['reasons'],['multiple_frames_unsupported'])


if __name__=='__main__':unittest.main()
