from pathlib import Path
from os import environ
from subprocess import run


def test_show_resource(tmpdir, monkeypatch):
    samplefile = Path(tmpdir, 'bar.traineddata')
    samplefile.write_text('bar')
    # simulate a Tesseract compiled with custom tessdata dir
    env = dict(environ)
    env.update(TESSDATA_PREFIX=str(tmpdir))
    r = run(['ocrd-tesserocr-recognize', '-C', 'bar.traineddata'],
            env=env, text=True, capture_output=True)
    assert not r.returncode, r.output

def test_list_all_resources(tmpdir, monkeypatch):
    samplefile = Path(tmpdir, 'foo.traineddata')
    samplefile.write_text('foo')
    # simulate a Tesseract compiled with custom tessdata dir
    env = dict(environ)
    env.update(TESSDATA_PREFIX=str(tmpdir))
    r = run(['ocrd-tesserocr-recognize', '-L'],
            env=env, text=True, capture_output=True)
    assert not r.returncode, r.output
