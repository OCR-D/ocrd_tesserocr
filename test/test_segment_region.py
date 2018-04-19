from test.base import TestCase, main, assets

from ocrd.resolver import Resolver
from ocrd_tesserocr.segment_region import TesserocrSegmentRegion

METS_HEROLD_SMALL = assets.url_of('SBB0000F29300010000/mets_one_file.xml')

class TestTesserocrRecognize(TestCase):

    def runTest(self):
        resolver = Resolver(cache_enabled=True)
        workspace = resolver.workspace_from_url(METS_HEROLD_SMALL)
        TesserocrSegmentRegion(workspace).process()
        workspace.save_mets()

if __name__ == '__main__':
    main()
