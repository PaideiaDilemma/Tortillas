'''This modules is used to analyze log data, that was parsed by LogParser.'''

from __future__ import annotations
from enum import Enum

import dataclasses

from .constants import TORTILLAS_EXPECT_PREFIX
from .utils import get_logger
from .tortillas_config import AnalyzeConfigEntry
from .test_specification import TestSpec


class TestStatus(Enum):
    '''Represents the outcome of a test run.'''
    PANIC = 1
    FAILED = 2
    TIMEOUT = 3
    SUCCESS = 4
    DISABLED = 5


@dataclasses.dataclass
class TestResult:
    '''Represents the result of a test run.'''
    status: TestStatus
    errors: list[str] = dataclasses.field(default_factory=list)
    retry: bool = False


class LogAnalyzer:
    '''
    Represent the result of a TestRun.
    The actuall result is determined by analyzing log data using
    the config entries in `TortillasConfig.analyze`.
    '''

    def __init__(self, test_repr: str, test_spec: TestSpec,
                 config: list[AnalyzeConfigEntry]):
        self.logger = get_logger(f'{test_repr} analyzer', prefix=True)

        self.test_repr = test_repr
        self.config = config
        self.expect_exit_codes = ([0] if not test_spec.expect_exit_codes
                                  else test_spec.expect_exit_codes)

        self.disabled = test_spec.disabled

        self.result = TestResult(TestStatus.SUCCESS)

    def analyze(self, log_data: dict[str, list[str]]) -> TestResult:
        '''Analyze `log_data` using the analyze configuration.'''
        for entry_name, logs in log_data.items():
            config_entry = self._get_config_entry_by_name(entry_name)
            status = (None if not config_entry.set_status else
                      TestStatus[config_entry.set_status])

            if not logs:
                continue

            if config_entry.mode == 'add_as_error':
                self.add_errors(logs, status)

            elif config_entry.mode == 'add_as_error_join':
                self.add_errors([f"```\n{''.join(logs)}```\n"], status)

            elif config_entry.mode == 'add_as_error_last':
                self.add_errors(logs[0:1], status)

            elif config_entry.mode == 'expect_stdout':
                self.check_expect_stdout(logs, status)

            elif config_entry.mode == 'exit_codes':
                self.check_exit_codes(logs, status)

        return self.result

    def _get_config_entry_by_name(self, name: str) -> AnalyzeConfigEntry:
        return next((entry for entry in self.config if entry.name == name))

    def _set_status(self, status: TestResult.Status | None):
        if not status:
            return

        self.logger.debug(f'Setting status to {status.name}')
        self.result.status = status

    def add_errors(self, errors: list[str],
                   status: TestResult.Status | None = None):
        '''Handle config mode \'ad_as_error\', set `status`, if supplied'''
        if not errors:
            return

        for error in errors:
            self.result.errors.append(error)

        self._set_status(status)

    def check_expect_stdout(self, logs,
                            status: TestResult.Status | None = None):
        '''Handle config mode \'expect_stdout\', set `status`, if supplied'''
        missing_output = False

        stdout = [line for line in logs
                  if not line.startswith(TORTILLAS_EXPECT_PREFIX)]

        expect_stdout = (line[len(TORTILLAS_EXPECT_PREFIX)-1:] for line in logs
                         if line.startswith(TORTILLAS_EXPECT_PREFIX))

        for expect in expect_stdout:
            if not any((expect.strip() in got for got in stdout)):
                self.result.errors.append(f'Expected output: {expect}')
                missing_output = True

        if missing_output:
            full_stdout = ''.join(line for line in stdout)
            self.result.errors.append(f'Actual output:\n```\n{full_stdout}\n```')
            self._set_status(status)

    def check_exit_codes(self, exit_codes: list[str],
                         status: TestResult.Status | None = None):
        '''Handle config mode \'exit_codes\', set `status`, if supplied'''
        if self.result.status == TestStatus.PANIC:
            return

        if not exit_codes:
            self.result.errors.append('Missing exit code!')
            if self.result.status == TestStatus.SUCCESS:
                self.result.status = TestStatus.FAILED
                return

        unexpected_exit_codes = False
        for exit_code in exit_codes:
            try:
                exit_code_int = int(exit_code)
            except ValueError:
                self.result.errors.append(f'Failed to parse exit code {exit_code}')
                self.result.status = TestStatus.FAILED
                self.result.retry = True
                return

            if exit_code_int not in self.expect_exit_codes:
                self.result.errors.append(f'Unexpected exit code {exit_code}')
                unexpected_exit_codes = True

        if unexpected_exit_codes:
            expected_codes = ', '.join(str(e)
                                       for e in self.expect_exit_codes)
            self.result.errors.append(
                    f'Expected exit code(s): {expected_codes}')
            self._set_status(status)
