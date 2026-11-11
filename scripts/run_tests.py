"""Run the test suite with the shims the HA test harness needs.

Usage: python scripts/run_tests.py [pytest args...]
"""

import os
import sys

# HA 2026.x aliases httpx to httpx2 on import and refuses if httpx is already loaded. The
# harness plugin imports httpx first, so homeassistant must be imported before pytest loads it.
import homeassistant  # noqa: F401  pylint: disable=unused-import
from homeassistant.const import MAJOR_VERSION, MINOR_VERSION

# The harness lags core releases. 2026.11 moved _clear_logger_overwrites into logger.helpers,
# which the 2026.10 harness still imports from logger. Only touch logger on those cores:
# importing it this early hits a circular import on older ones (seen on 2024.1).
if (MAJOR_VERSION, MINOR_VERSION) >= (2026, 11):
    import homeassistant.components.logger as ha_logger

    if not hasattr(ha_logger, "_clear_logger_overwrites"):
        from homeassistant.components.logger.helpers import _clear_logger_overwrites

        ha_logger._clear_logger_overwrites = _clear_logger_overwrites

import pytest  # pylint: disable=wrong-import-position

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.exit(
    pytest.main(
        [
            "--rootdir",
            REPO_ROOT,
            "-c",
            os.path.join(REPO_ROOT, "pyproject.toml"),
            os.path.join(REPO_ROOT, "tests"),
            *sys.argv[1:],
        ]
    )
)
