"""Test configuration for NEIS School."""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

HAS_HOME_ASSISTANT = importlib.util.find_spec("homeassistant") is not None

if HAS_HOME_ASSISTANT:
    pytest_plugins = "pytest_homeassistant_custom_component"
else:
    root = types.ModuleType("custom_components")
    root.__path__ = [str(Path(__file__).parents[1] / "custom_components")]
    sys.modules["custom_components"] = root
    package = types.ModuleType("custom_components.neis_school")
    package.__path__ = [
        str(Path(__file__).parents[1] / "custom_components" / "neis_school")
    ]
    sys.modules["custom_components.neis_school"] = package


if HAS_HOME_ASSISTANT:

    @pytest.fixture(autouse=True)
    def auto_enable_custom_integrations(enable_custom_integrations):
        """Enable custom integrations for every test."""
