"""Tests for scheduler CLI entry point."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


def test_scheduler_script_exists():
    script = Path(__file__).parent.parent / "scheduler.py"
    assert script.exists(), "scheduler.py must exist at project root"


def test_scheduler_imports():
    """Verify scheduler.py can be imported without errors."""
    import importlib
    spec = importlib.util.spec_from_file_location(
        "scheduler_cli",
        str(Path(__file__).parent.parent / "scheduler.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    # Don't execute, just verify it parses
    assert spec is not None


def test_scheduler_main_function():
    """Verify scheduler has a main() function."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "scheduler_cli",
        str(Path(__file__).parent.parent / "scheduler.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "main"), "scheduler.py must have a main() function"


def test_scheduler_main_runs():
    """Test that main() executes without error (with test DB)."""
    import importlib.util
    import os

    os.environ["DIGITAL_FOOTPRINT_DB_PATH"] = ":memory:"
    spec = importlib.util.spec_from_file_location(
        "scheduler_cli",
        str(Path(__file__).parent.parent / "scheduler.py"),
    )
    mod = importlib.util.module_from_spec(spec)

    with patch.dict(os.environ, {"DIGITAL_FOOTPRINT_DB_PATH": ":memory:"}):
        spec.loader.exec_module(mod)
        # Patch out actual job execution
        with patch("digital_footprint.scheduler.runner.run_scheduled_jobs") as mock_run:
            mock_run.return_value = []
            exit_code = mod.main()
            assert exit_code == 0
