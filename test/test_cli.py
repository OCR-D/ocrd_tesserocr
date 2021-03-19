from test.base import CapturingTestCase as TestCase, main, assets, skip
from os import environ
from pathlib import Path
from ocrd_utils import pushd_popd
from ocrd_tesserocr.cli import ocrd_tesserocr_recognize
from ocrd_utils import disableLogging

class TestTesserocrCli(TestCase):

    # def setUp(self):
        # initLogging()

    def tearDown(self):
        del(environ['TESSDATA_PREFIX'])
        disableLogging()

    # XXX doesn't work because shutil.copyfileobj to stdout won't be captured by self.invoke_cli
    # def test_show_resource(self):
    #     with pushd_popd(tempdir=True) as tempdir:
    #         samplefile = Path(tempdir, 'bar.traineddata')
    #         samplefile.write_text('bar')
    #         environ['TESSDATA_PREFIX'] = tempdir
    #         code, out, err = self.invoke_cli(ocrd_tesserocr_recognize, ['-C', 'bar'])
    #         assert not code
    #         assert out == 'bar'

    def test_list_all_resources(self):
        with pushd_popd(tempdir=True) as tempdir:
            samplefile = Path(tempdir, 'foo.traineddata')
            samplefile.write_text('foo')
            environ['TESSDATA_PREFIX'] = tempdir
            _, out, _ = self.invoke_cli(ocrd_tesserocr_recognize, ['-L'])
            assert out == str(samplefile) + '\n'

if __name__ == '__main__':
    main(__file__)
