# pylint: disable=unused-import

import os
import sys
import shutil
from tempfile import mkdtemp
from unittest import TestCase as VanillaTestCase, main as unittests_main, skip # pylint: disable=unused-import
import pytest

from test.assets import assets
from ocrd.resolver import Resolver
from ocrd_utils import initLogging

PWD = os.path.dirname(os.path.realpath(__file__))
sys.path.append(PWD + '/../ocrd')

def main(fn=None):
    if fn:
        sys.exit(pytest.main([fn]))
    else:
        unittests_main()

class TestCase(VanillaTestCase):
    METS_HEROLD_SMALL = None

    @classmethod
    def setUpClass(cls):
        initLogging()

    # we must intercept and reinstate CWD, because Processor.__init__ does chdir,
    # but setUp needs to rm that copy afterwards; so the next test would end up
    # in a non-existing CWD, causing os.getcwd() to fail
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.old_cwd = os.getcwd()
        self.resolver = Resolver()
        self.workspace = None
    def tearDown(self):
        os.chdir(self.old_cwd)
        if os.path.exists(self.workspace.directory):
            shutil.rmtree(self.workspace.directory)
        self.workspace = None
    # isolate test methods from each other by cloning the asset workspace afresh
    def setUp(self):
        self.workspace = self.resolver.workspace_from_url(
            self.METS_HEROLD_SMALL, download=True,
            dst_dir=mkdtemp(prefix=self.__class__.__name__))

class CapturingTestCase(VanillaTestCase):
    """
    A TestCase that needs to capture stderr/stdout and invoke click CLI.
    """

    @pytest.fixture(autouse=True)
    def _setup_pytest_capfd(self, capfd):
        self.capfd = capfd

    def invoke_cli(self, cli, args):
        """
        Substitution for click.CliRunner.invooke that works together nicely
        with unittests/pytest capturing stdout/stderr.
        """
        self.capture_out_err()  # XXX snapshot just before executing the CLI
        code = 0
        sys.argv[1:] = args # XXX necessary because sys.argv reflects pytest args not cli args
        try:
            cli.main(args=args)
        except SystemExit as e:
            code = e.code
        out, err = self.capture_out_err()
        return code, out, err

    def capture_out_err(self):
        return self.capfd.readouterr()

