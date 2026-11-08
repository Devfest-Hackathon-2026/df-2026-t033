from pathlib import Path
import tempfile
import unittest
import numpy as np
from PIL import Image
from fingerprint_model.pattern import extract,descriptor,save_templates,load_templates,predict,template_scores


class PatternTests(unittest.TestCase):
    def test_blank_and_uniform_skin_do_not_produce_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory)
            white=base/'white.png';Image.new('RGB',(512,512),'white').save(white)
            with self.assertRaisesRegex(ValueError,'insufficient_foreground'): extract(white,'phone')
            skin=base/'skin.png';Image.new('RGB',(512,512),(210,150,110)).save(skin)
            item=extract(skin,'phone')
            self.assertFalse(item['quality']['readable'])
            model=(np.zeros((3,256,2)),np.ones((3,256)),np.arange(3),{})
            self.assertIsNone(predict(item,model)['candidate'])
            with self.assertRaisesRegex(ValueError,'invalid_manual_roi'): extract(skin,'phone',[-1,0,512,512])

    def test_no_common_support_does_not_default_to_arch(self):
        item={'angles':np.ones((256,2)), 'weights':np.r_[np.ones(30),np.zeros(226)],
              'quality':{'readable':True,'valid_blocks':30}}
        weights=np.tile(np.r_[np.zeros(100),np.ones(50),np.zeros(106)],(3,1))
        result=predict(item,(np.ones((3,256,2)),weights,np.arange(3),{}))
        self.assertEqual(result['decision'],'insufficient_match')
        self.assertIsNone(result['candidate'])

    def test_direction_polarity_and_template_roundtrip(self):
        y,x=np.mgrid[:512,:512]
        im=np.uint8(128+60*np.sin(x*.25+y*.04))
        mask=Image.new('L',(512,512),255)
        positive=descriptor(Image.fromarray(im),mask)
        negative=descriptor(Image.fromarray(255-im),mask)
        self.assertTrue(positive['quality']['readable'])
        self.assertGreater(float(np.mean(np.sum(positive['angles']*negative['angles'],axis=1))),.9)
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'templates.npz'
            save_templates(file,[positive,positive,positive],[0,1,2],{'domain':'test-fixture'})
            model=load_templates(file)
            before=template_scores(positive,model[0],model[1],model[2])[0]
            after=template_scores(positive,*load_templates(file)[:3])[0]
            np.testing.assert_array_equal(before,after)
            self.assertIsNone(predict(positive,model)['verified_label'])


if __name__=='__main__':unittest.main()
