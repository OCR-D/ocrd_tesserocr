from ocrd.resolver import Resolver
from ocrd_utils import pushd_popd, initLogging
from pytest import fixture

from test.assets import assets as assets

METS_KANT_BINARIZED = assets.url_of('kant_aufklaerung_1784-binarized/data/mets.xml')
METS_HEROLD_SMALL = assets.url_of('SBB0000F29300010000/data/mets_one_file.xml')
METS_GUTACHTEN = assets.url_of('gutachten/data/mets.xml')

@fixture
def workspace_kant_binarized(tmpdir):
    initLogging()
    with pushd_popd(tmpdir):
        yield Resolver().workspace_from_url(METS_KANT_BINARIZED, dst_dir=tmpdir, download=True)

@fixture
def workspace_herold_small(tmpdir):
    initLogging()
    with pushd_popd(tmpdir):
        yield Resolver().workspace_from_url(METS_HEROLD_SMALL, dst_dir=tmpdir, download=True)

@fixture
def workspace_gutachten(tmpdir):
    initLogging()
    with pushd_popd(tmpdir):
        yield Resolver().workspace_from_url(METS_GUTACHTEN, dst_dir=tmpdir, download=True)

