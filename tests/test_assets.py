import io
import hashlib
import pytest
from parametric_mac import assets


def test_verified_download_and_repeat(tmp_path, monkeypatch):
    data = b'valid fixture'
    monkeypatch.setattr(assets, 'FILES', {'test.wav': hashlib.sha256(data).hexdigest()})
    monkeypatch.setattr(assets, 'urlopen', lambda *a, **kw: io.BytesIO(data))
    assets.download_inputs(tmp_path)
    assets.download_inputs(tmp_path)
    assert (tmp_path / 'test.wav').read_bytes() == data


def test_corrupt_download_is_not_installed(tmp_path, monkeypatch):
    monkeypatch.setattr(assets, 'FILES', {'test.wav': 'wrong'})
    monkeypatch.setattr(assets, 'urlopen', lambda *a, **kw: io.BytesIO(b'bad'))
    with pytest.raises(ValueError, match='Checksum mismatch'):
        assets.download_inputs(tmp_path)
    assert not list(tmp_path.iterdir())


def test_existing_file_is_not_overwritten(tmp_path, monkeypatch):
    monkeypatch.setattr(assets, 'FILES', {'test.wav': 'wrong'})
    (tmp_path / 'test.wav').write_bytes(b'user audio')
    with pytest.raises(ValueError, match='different contents'):
        assets.download_inputs(tmp_path)
    assert (tmp_path / 'test.wav').read_bytes() == b'user audio'
