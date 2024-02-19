from ocrd.resolver import Resolver
from ocrd_utils import pushd_popd
from pytest import fixture

from test.assets import assets as assets

METS_KANT_BINARIZED = assets.url_of('kant_aufklaerung_1784-binarized/data/mets.xml')
METS_HEROLD_SMALL = assets.url_of('SBB0000F29300010000/data/mets_one_file.xml')

@fixture
def workspace_kant_binarized():
    with pushd_popd(tempdir=True) as tempdir:
        yield Resolver().workspace_from_url(METS_KANT_BINARIZED, dst_dir=tempdir)

@fixture
def workspace_herold_small():
    with pushd_popd(tempdir=True) as tempdir:
        yield Resolver().workspace_from_url(METS_HEROLD_SMALL, dst_dir=tempdir)

