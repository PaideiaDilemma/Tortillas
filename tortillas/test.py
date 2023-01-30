from __future__ import annotations

from utils import get_logger
from constants import TestStatus, TEST_FOLDER_PATH, TEST_RUN_DIR
from tortillas_config import TortillasConfig
from test_config import TestConfig


class Test:
    def __init__(self, name: str, num: int, src_folder: str,
                 config: TortillasConfig, pra_selector_programm: str = ''):
        self.name = name
        self.run_number = num

        self.test_file = rf'{src_folder}/{TEST_FOLDER_PATH}/{self.name}.c'
        self.config = TestConfig(self.name, self.test_file)

        self.pra_selector_programm = pra_selector_programm

        self.logger = get_logger(repr(self), prefix=True)

        self.result = TestResult(self, config)

    def __eq__(self, other) -> bool:
        if isinstance(other, Test):
            return self.name == other.name
        return NotImplemented

    def __repr__(self):
        repr = self.name
        if self.run_number > 1:
            repr += f'Run {self.run_number}'
        if self.pra_selector_programm:
            repr += f' {self.pra_selector_programm}'
        return repr

    def set_pra_selector_programm(self, pra_selector: str):
        self.pra_selector_programm = pra_selector
        self.logger = get_logger(repr(self), prefix=True)

    def get_tmp_dir(self) -> str:
        return rf"{TEST_RUN_DIR}/{repr(self).lower().replace(' ', '-')}"


class TestResult:
    def __init__(self, test: Test, config: TortillasConfig):
        self.logger = get_logger(f'{repr(test)} result', prefix=True)

        self.test_name = test.name
        self.test_config = test.config

        self.config = config.analyze
        self.expect_exit_codes = ([0] if not test.config.expect_exit_codes
                                  else test.config.expect_exit_codes)

        self.retry = False

        self.errors: list[str] = []
        self.status: TestStatus
        if self.test_config.disabled:
            self.status = TestStatus.DISABLED
            return

    def set_status(self, status: TestStatus | None):
        if not status:
            return

        self.logger.debug(f'Setting status to {status.name}')
        self.status = status

    def add_execution_error(self, error: str):
        self.errors.append(error)
        self.status = TestStatus.FAILED

    def add_errors(self, log_data_entry: list[str],
                   status: TestStatus | None = None):
        if not log_data_entry:
            return

        for error in log_data_entry:
            self.errors.append(error)

        self.set_status(status)

    def check_expect_stdout(self, expect_stdout: list[str],
                            stdout: list[str],
                            status: TestStatus | None = None):
        if not expect_stdout:
            return

        missing_output = False

        for expect in expect_stdout:
            if not any((expect in got for got in stdout)):
                self.errors.append(f'Expected output: {expect}')
                missing_output = True

        if missing_output:
            full_stdout = ''.join(line for line in stdout)
            self.errors.append(f'Actual output:\n{full_stdout}')
            self.set_status(status)

    def analyze_exit_codes(self, exit_codes: list[str],
                           status: TestStatus | None = None):
        if not exit_codes:
            self.errors.append('Missing exit code!')
            if self.status == TestStatus.SUCCESS:
                self.status = TestStatus.FAILED
                return

        for exit_code in exit_codes:
            unexpected_exit_codes = False
            try:
                exit_code_int = int(exit_code)
            except ValueError:
                self.errors.append(f'Failed to parse exit code {exit_code}')
                self.status = TestStatus.FAILED
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
                self.set_status(status)

    def analyze(self, log_data: dict[str, list[str]]):
        self.status = TestStatus.SUCCESS

        for analyze_config_entry in self.config:
            log_data_name = analyze_config_entry.name
            status = (None if not analyze_config_entry.status else
                      TestStatus[analyze_config_entry.status])

            self.logger.debug(f'Analyzing {analyze_config_entry.name}')

            if analyze_config_entry.mode == 'add_as_error':
                self.add_errors(log_data[log_data_name], status)

            elif analyze_config_entry.mode == 'add_as_error_join':
                self.add_errors(''.join(log_data[log_data_name]), status)

            elif analyze_config_entry.mode == 'expect_stdout':
                self.check_expect_stdout(log_data[log_data_name],
                                         log_data['stdout'], status
                                         )

            elif analyze_config_entry.mode == 'exit_codes':
                self.analyze_exit_codes(log_data[log_data_name], status)

            if self.status == TestStatus.PANIC:
                break
