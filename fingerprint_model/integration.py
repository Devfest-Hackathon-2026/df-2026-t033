"""Stable, in-memory integration API for experimental pattern candidates."""
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image
from . import pattern

ASSET = Path(__file__).parent / 'assets' / 'pattern-v1' / 'templates.npz'
SCHEMA_VERSION = 'fingerprint-candidate-v1'


class FingerprintClassifier:
    """Load once per backend worker. No image files or prediction logs are written."""

    def __init__(self, model_path=None):
        path = Path(model_path) if model_path is not None else ASSET
        self.model_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        if model_path is None:
            expected = path.with_name('SHA256.txt').read_text().split()[0]
            if self.model_sha256 != expected:
                raise ValueError('bundled_model_checksum_mismatch')
        self.model = pattern.load_templates(path)

    def predict(self, image, *, domain='phone', roi=None):
        """image: bytes or local path; roi: EXIF-oriented (left, top, right, bottom)."""
        base = dict(schema_version=SCHEMA_VERSION, candidate=None, decision='error',
                    verified_label=None, quality={}, reasons=[], needs_review=True,
                    experimental=True, method=pattern.VERSION,
                    model_sha256=self.model_sha256)
        try:
            if not isinstance(image, (bytes, str, Path)):
                raise ValueError('invalid_image_input_type')
            if domain not in ('phone', 'scan'):
                raise ValueError('invalid_domain')
            if roi is not None and (not isinstance(roi, (tuple,list)) or len(roi)!=4
                    or any(type(x) is not int for x in roi)):
                raise ValueError('invalid_manual_roi')
            result = pattern.predict(pattern.extract(image, domain, roi), self.model)
            return {**base, **result}
        except (ValueError, OSError, Image.DecompressionBombError) as exc:
            known = {'invalid_image_input_type','invalid_domain','invalid_manual_roi',
                     'image_size_limit','unsupported_image_format','multiple_frames_unsupported',
                     'unsupported_image_dimensions','insufficient_foreground_retake_or_adjust_roi',
                     'no_interior_foreground'}
            reason = str(exc) if str(exc) in known else 'invalid_or_unreadable_image'
            base['reasons'] = [reason]
            if reason in {'insufficient_foreground_retake_or_adjust_roi','no_interior_foreground'}:
                base['decision'] = 'retake'
            return base


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--domain', choices=['phone','scan'], default='phone')
    parser.add_argument('--roi', help='EXIF-oriented x0,y0,x1,y1, optional for a prepared ROI')
    args=parser.parse_args()
    try:
        roi=[int(v) for v in args.roi.split(',')] if args.roi else None
    except ValueError:
        parser.error('ROI must contain four integers')
    result=FingerprintClassifier().predict(args.image,domain=args.domain,roi=roi)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 2 if result['decision']=='error' else 0


if __name__=='__main__':raise SystemExit(main())
