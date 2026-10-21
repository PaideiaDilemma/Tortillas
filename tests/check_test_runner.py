from pathlib import Path

import pytest

from tortillas.log_analyzer import TestStatus
from tortillas.progress_bar import ProgressBar
from tortillas.test_runner import TestRunner
from tortillas.test_specification import TestSpec
from tortillas.tortillas_config import TortillasConfig

TEST_SPEC_PATH = Path("./tests/assets/test_spec.txt")


def _config() -> TortillasConfig:
    return TortillasConfig(Path("./tortillas_config.yml"))


def _runner(test_names: list[str]) -> TestRunner:
    specs = [TestSpec(name, TEST_SPEC_PATH) for name in test_names]
    runner = TestRunner(specs, 1, "x86_64", _config(), ProgressBar(True))

    for run in runner.test_runs:
        run.result.status = TestStatus.SUCCESS

    return runner


def _table_lines(summary: str) -> list[str]:
    return [line for line in summary.splitlines() if line.startswith("|")]


def test_summary_renders_short_names(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("tortillas.test_runner.SWEB_BUILD_DIR", tmp_path)

    summary = _runner(["short_test"]).get_markdown_test_summary()

    assert "short_test" in summary
    assert "SUCCESS" in summary


def test_summary_grows_table_for_long_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr("tortillas.test_runner.SWEB_BUILD_DIR", tmp_path)
    long_name = "pthread_cancel_while_joining" + "g" * 50

    summary = _runner([long_name]).get_markdown_test_summary()

    assert long_name in summary
    # All table lines share one width, so the columns stay aligned.
    assert len({len(line) for line in _table_lines(summary)}) == 1


def test_summary_marks_disabled_tests(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("tortillas.test_runner.SWEB_BUILD_DIR", tmp_path)
    disabled_spec = TestSpec("disabled_test", TEST_SPEC_PATH)
    disabled_spec.disabled = True

    runner = TestRunner([disabled_spec], 1, "x86_64", _config(), ProgressBar(True))
    runner.success = True

    summary = runner.get_markdown_test_summary()

    assert "disabled_test" in summary
    assert "DISABLED" in summary
