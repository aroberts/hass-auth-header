import importlib
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CUSTOM_COMPONENTS_DIR = os.path.join(REPO_ROOT, "custom_components")


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Make HA's loader find this repo's integration.

    Harness releases ship their own custom_components package, or none. Whichever one gets
    imported, add this repo's directory to its search path.
    """
    try:
        import custom_components  # pylint: disable=import-outside-toplevel
    except ImportError:
        sys.path.insert(0, REPO_ROOT)
        custom_components = importlib.import_module("custom_components")
    if CUSTOM_COMPONENTS_DIR not in list(custom_components.__path__):
        custom_components.__path__.append(CUSTOM_COMPONENTS_DIR)
    yield
