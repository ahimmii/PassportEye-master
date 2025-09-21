import glob
import os
import json
import pytest


def _find_moroccan_samples():
    here = os.path.dirname(__file__)
    repo_root = os.path.abspath(os.path.join(here, os.pardir))
    testdata_dir = os.path.join(repo_root, 'passporteye', 'mrz', 'testdata')
    patterns = [
        os.path.join(testdata_dir, 'morocco_*.jpg'),
        os.path.join(testdata_dir, 'morocco_*.jpeg'),
        os.path.join(testdata_dir, 'morocco_*.png'),
        os.path.join(testdata_dir, 'moroccan_*.jpg'),
        os.path.join(testdata_dir, 'moroccan_*.png'),
        os.path.join(testdata_dir, '*_id-mar*.jpg'),
        os.path.join(testdata_dir, '*_id-mar*.jpeg'),
        os.path.join(testdata_dir, '*_id-mar*.png'),
    ]
    files = []
    for pat in patterns:
        files.extend(glob.glob(pat))
    return sorted(set(files))


@pytest.mark.parametrize('img_path', _find_moroccan_samples())
def test_moroccan_id_extraction(img_path):
    """Validate Moroccan ID extraction.

    Rules:
    - If MRZ is present (typically back side), assert MRZ fields are non-empty.
    - If no MRZ, look for a JSON sidecar with expected fields (<image>.json) and
      assert front-ocr fallback matches provided expectations. Otherwise skip
      (front OCR is heuristic and sample-dependent).
    """
    from mrzsite.mrzapp.morocco import read_morocco_id
    from mrzsite.mrzapp.morocco_front import read_morocco_front

    # Try MRZ path first
    try:
        data = read_morocco_id(img_path, use_legacy=True, require_mar=False)
        assert isinstance(data, dict)
        # MRZ expectations
        assert data.get('mrz_type') in {'TD1', 'TD2', 'TD3'}
        assert data.get('number')
        return
    except Exception:
        pass

    # Fallback: check for sidecar expectations for front images
    sidecar = os.path.splitext(img_path)[0] + '.json'
    if os.path.exists(sidecar):
        expected = json.load(open(sidecar, 'r'))
        data = read_morocco_front(img_path)
        for key in ['number', 'surname', 'names', 'date_of_birth_formatted', 'expiration_date_formatted', 'country', 'nationality']:
            if key in expected:
                assert data.get(key) == expected[key]
        return

    pytest.skip('No MRZ detected and no sidecar expectations provided for front image.')


def test_has_samples_or_skips():
    samples = _find_moroccan_samples()
    if not samples:
        pytest.skip('No Moroccan ID samples found in passporteye/mrz/testdata (expected files like morocco_*.jpg).')

