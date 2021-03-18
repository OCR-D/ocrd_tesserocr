from test.base import CapturingTestCase as TestCase, main, assets, skip
from os import environ
from pathlib import Path
from ocrd_utils import pushd_popd
from ocrd_tesserocr.cli import ocrd_tesserocr_recognize

class TestTesserocrCli(TestCase):

    def test_list_all_resources(self):
        with pushd_popd(tempdir=True) as tempdir:
            samplefile = Path(tempdir, 'foo.traineddata')
            samplefile.write_text('foo')
            environ['TESSDATA_PREFIX'] = tempdir
            _, out, _ = self.invoke_cli(ocrd_tesserocr_recognize, ['-L'])
            assert out == str(samplefile) + '\n'

if __name__ == '__main__':
    main(__file__)
