#METS_HEROLD_SMALL = assets.url_of('SBB0000F29300010000/data/mets_one_file.xml')
# as long as #96 remains, we cannot use workspaces which have local relative files:
from tempfile import mkdtemp
from ocrd.resolver import Resolver
from pytest import fixture

from test.assets import assets as assets

METS_KANT_BINARIZED = assets.url_of('kant_aufklaerung_1784-binarized/data/mets.xml')
METS_HEROLD_SMALL = assets.url_of('SBB0000F29300010000/data/mets_one_file.xml')

@fixture
def workspace_kant_binarized():
    return Resolver().workspace_from_url(METS_KANT_BINARIZED, download=True, dst_dir=mkdtemp(prefix='pytest_ocrd_tesserocr'))

@fixture
def workspace_herold_small():
    return Resolver().workspace_from_url(METS_HEROLD_SMALL, download=True, dst_dir=mkdtemp(prefix='pytest_ocrd_tesserocr'))

