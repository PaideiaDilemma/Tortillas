'''This modules is used to analyze log data, that was parsed by LogParser.'''

from __future__ import annotations
from enum import Enum

from .utils import get_logger
from .tortillas_config import AnalyzeConfigEntry
from .test_specification import TestSpec


class TestResult:
    '''
    Represent the result of a TestRun.
    The actuall result is determined by analyzing log data using
    the config entries in `TortillasConfig.analyze`.
    '''

    class Status(Enum):
        '''Represents the final result of a test run.'''
        DISABLED = 1
        SUCCESS = 2
        PANIC = 3
        FAILED = 4

    def __init__(self, test_repr: str, test_spec: TestSpec,
                 config: list[AnalyzeConfigEntry]):
        self.logger = get_logger(f'{test_repr} result', prefix=True)

        self.test_repr = test_repr
        self.config = config
        self.expect_exit_codes = ([0] if not test_spec.expect_exit_codes
                                  else test_spec.expect_exit_codes)

        self.retry = False

        self.errors: list[str] = []
        self.status: self.Status
        if test_spec.disabled:
            self.status = self.Status.DISABLED
            return

    def analyze(self, log_data: dict[str, list[str]]):
        '''Analyze `log_data` using the analyze configuration.'''
        self.status = self.Status.SUCCESS

        for analyze_config_entry in self.config:
            log_data_name = analyze_config_entry.label
            status = (None if not analyze_config_entry.status else
                      self.Status[analyze_config_entry.status])

            self.logger.debug(f'Analyzing {analyze_config_entry.label}')

            if not log_data[log_data_name]:
                continue

            if analyze_config_entry.mode == 'add_as_error':
                self.add_errors(log_data[log_data_name], status)

            elif analyze_config_entry.mode == 'add_as_error_join':
                self.add_errors([''.join(log_data[log_data_name])], status)

            elif analyze_config_entry.mode == 'expect_stdout':
                self.check_expect_stdout(log_data[log_data_name],
                                         log_data['stdout'], status
                                         )

            elif analyze_config_entry.mode == 'exit_codes':
                self.check_exit_codes(log_data[log_data_name], status)

    def _set_status(self, status: TestResult.Status | None):
        if not status:
            return

        self.logger.debug(f'Setting status to {status.name}')
        self.status = status

    def add_execution_error(self, error: str):
        '''
        Add an `error` during execution. Used for example, if a timeout occurs.
        '''
        self.errors.append(error)
        self.status = self.Status.FAILED

    def add_errors(self, log_data_entry: list[str],
                   status: TestResult.Status | None = None):
        '''Handle config mode \'ad_as_error\', set `status`, if supplied'''
        if not log_data_entry:
            return

        for error in log_data_entry:
            self.errors.append(error)

        self._set_status(status)

    def check_expect_stdout(self, expect_stdout: list[str],
                            stdout: list[str],
                            status: TestResult.Status | None = None):
        '''Handle config mode \'expect_stdout\', set `status`, if supplied'''
        if not expect_stdout:
            return

        missing_output = False

        for expect in expect_stdout:
            if not any((expect.strip() in got for got in stdout)):
                self.errors.append(f'Expected output: {expect}')
                missing_output = True

        if missing_output:
            full_stdout = ''.join(line for line in stdout)
            self.errors.append(f'Actual output:\n{full_stdout}')
            self._set_status(status)

    def check_exit_codes(self, exit_codes: list[str],
                         status: TestResult.Status | None = None):
        '''Handle config mode \'exit_codes\', set `status`, if supplied'''
        if self.status == self.Status.PANIC:
            return

        if not exit_codes:
            self.errors.append('Missing exit code!')
            if self.status == self.Status.SUCCESS:
                self.status = self.Status.FAILED
                return

        unexpected_exit_codes = False
        for exit_code in exit_codes:
            try:
                exit_code_int = int(exit_code)
            except ValueError:
                self.errors.append(f'Failed to parse exit code {exit_code}')
                self.status = self.Status.FAILED
                self.retry = True
                return

            if exit_code_int not in self.expect_exit_codes:
                self.errors.append(f'Unexpected exit code {exit_code}')
                unexpected_exit_codes = True

        if unexpected_exit_codes:
            expected_codes = ', '.join(str(e)
                                       for e in self.expect_exit_codes)
            self.errors.append(
                    f'Expected exit code(s): {expected_codes}')
            self._set_status(status)
