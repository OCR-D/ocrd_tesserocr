from click.testing import CliRunner

from test.base import main
from pathlib import Path

runner = CliRunner()

def test_show_resource(tmpdir, monkeypatch):
    samplefile = Path(tmpdir, 'bar.traineddata')
    samplefile.write_text('bar')
    # simulate a Tesseract compiled with custom tessdata dir
    monkeypatch.setenv('TESSDATA_PREFIX', str(tmpdir))
    # does not work (thus, tesserocr must not have been loaded already):
    #monkeypatch.delitem(sys.modules, 'tesserocr')
    # envvars influence tesserocr's module initialization
    from ocrd_tesserocr.cli import ocrd_tesserocr_recognize
    r = runner.invoke(ocrd_tesserocr_recognize, ['-C', 'bar.traineddata'])
    assert not r.exit_code, r.output
    # XXX doesn't work <del>because shutil.copyfileobj to stdout won't be captured
    # by self.invoke_cli</del> Not sure why it does not work :(
    # assert r.output == 'bar'

def test_list_all_resources(tmpdir, monkeypatch):
    samplefile = Path(tmpdir, 'foo.traineddata')
    samplefile.write_text('foo')
    # simulate a Tesseract compiled with custom tessdata dir
    monkeypatch.setenv('TESSDATA_PREFIX', str(tmpdir))
    # envvars influence tesserocr's module initialization
    from ocrd_tesserocr.cli import ocrd_tesserocr_recognize
    r = runner.invoke(ocrd_tesserocr_recognize, ['-L'])
    assert not r.exit_code
    # XXX same problem
    # assert r.output == str(samplefile) + '\n'

if __name__ == '__main__':
    main(__file__)
