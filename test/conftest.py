from multiprocessing import Process
from time import sleep
from pytest import fixture

from ocrd import Resolver, Workspace, OcrdMetsServer
from ocrd_utils import pushd_popd, initLogging, setOverrideLogLevel, disableLogging, config

from test.assets import assets as assets

CONFIGS = ['', 'pageparallel', 'metscache', 'pageparallel+metscache']

@fixture(params=CONFIGS)
def workspace(tmpdir, pytestconfig, request):
    def _make_workspace(workspace_path):
        initLogging()
        if pytestconfig.getoption('verbose') > 0:
            setOverrideLogLevel('DEBUG')
        with pushd_popd(tmpdir):
            if 'metscache' in request.param:
                config.OCRD_METS_CACHING = True
                print("enabled METS caching")
            directory = str(tmpdir)
            resolver = Resolver()
            workspace = resolver.workspace_from_url(workspace_path, dst_dir=directory, download=True)
            if 'pageparallel' in request.param:
                config.OCRD_MAX_PARALLEL_PAGES = 2
                print("enabled page-parallel processing")
                def _start_mets_server(*args, **kwargs):
                    print("running with METS server")
                    server = OcrdMetsServer(*args, **kwargs)
                    server.startup()
                process = Process(target=_start_mets_server,
                          kwargs={'workspace': workspace, 'url': 'mets.sock'})
                process.start()
                sleep(1)
                workspace = Workspace(resolver, directory, mets_server_url='mets.sock')
                yield workspace
                process.terminate()
            else:
                yield workspace
        config.reset_defaults()
        disableLogging() # avoid writing to closed streams
    return _make_workspace

@fixture
def workspace_kant_binarized(workspace):
    yield from workspace(assets.url_of('kant_aufklaerung_1784-binarized/data/mets.xml'))

@fixture
def workspace_herold_small(workspace):
    yield from workspace(assets.url_of('SBB0000F29300010000/data/mets_one_file.xml'))

@fixture
def workspace_gutachten(workspace):
    yield from workspace(assets.url_of('gutachten/data/mets.xml'))
