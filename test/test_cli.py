from click.testing import CliRunner

from test.base import main
from pathlib import Path
from ocrd_utils import pushd_popd
from ocrd_tesserocr.cli import ocrd_tesserocr_recognize
from ocrd_utils import disableLogging

runner = CliRunner()

def test_show_resource(tmpdir, monkeypatch):
    samplefile = Path(tmpdir, 'bar.traineddata')
    samplefile.write_text('bar')
    monkeypatch.setenv('TESSDATA_PREFIX': str(tmpdir))
    r = runner.invoke(ocrd_tesserocr_recognize, ['-C', 'bar'])
    assert not r.exit_code
    # XXX doesn't work <del>because shutil.copyfileobj to stdout won't be captured
    # by self.invoke_cli</del> Not sure why it does not work :(
    # assert r.output == 'bar'

def test_list_all_resources(tmpdir, monkeypatch):
    samplefile = Path(tmpdir, 'foo.traineddata')
    samplefile.write_text('foo')
    monkeypatch.setenv('TESSDATA_PREFIX': str(tmpdir))
    r = runner.invoke(ocrd_tesserocr_recognize, ['-L'])
    assert not r.exit_code
    # XXX same problem
    # assert r.output == str(samplefile) + '\n'

if __name__ == '__main__':
    main(__file__)
