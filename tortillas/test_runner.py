'''This modules contains the top level interface for running tests.'''

from __future__ import annotations
from typing import Callable

import sys
import time
import pathlib
import threading
import subprocess

from .utils import get_logger
from .constants import (SWEB_BUILD_DIR, TEST_RUN_DIR, QEMU_VMSTATE_TAG,
                        INT_SYSCALL)
from .tortillas_config import TortillasConfig
from .test_specification import TestSpec
from .test_result import TestResult
from .log_parser import LogParser
from .progress_bar import ProgressBar
from .qemu_interface import QemuInterface, InterruptWatchdog


class TestRun:
    '''
    A wrapper around TestSpec and TestResult, that respresents a test run.
    '''

    def __init__(self, test_spec: TestSpec, num: int, config: TortillasConfig):
        self.name = test_spec.test_name
        self.run_number = num
        self.spec = test_spec

        self.logger = get_logger(repr(self), prefix=True)

        self.result = TestResult(test_repr=repr(self),
                                 test_spec=self.spec,
                                 config=config.analyze)

        tmp_dir_name = repr(self).lower().replace(' ', '-')
        self.tmp_dir = rf'{TEST_RUN_DIR}/{tmp_dir_name}'

    def analyze(self):
        '''
        Call this to run the parse and analyze the logfile of this test run.
        '''
        parser = LogParser(log_file_path=f'{self.tmp_dir}/out.log',
                           logger=self.logger,
                           config=self.result.config)

        self.result.analyze(parser.parse())

    def get_tmp_dir(self) -> str:
        '''Get the temporary directory of the test run'''
        return self.tmp_dir

    def __eq__(self, other) -> bool:
        if isinstance(other, TestRun):
            return self.name == other.name
        return NotImplemented

    def __repr__(self):
        ret = self.name
        if self.run_number:
            ret += f' Run {self.run_number}'
        return ret


class TestRunner:
    '''
    Facilitates the creation of a qemu snapshot and
    the execution of all test runs.

    Also provides a summary of all test runs via `get_markdown_test_summary`.
    '''

    def __init__(self,  specs: list[TestSpec], repeat: int, architecture: str,
                 config: TortillasConfig, progress_bar: ProgressBar):
        self.logger = get_logger('global')

        self.architecture = architecture
        self.progress_bar = progress_bar
        self.config = config

        self.test_runs = [TestRun(spec, num, config)
                          for spec in specs if not spec.disabled
                          for num in range(repeat)]

        self.disabled_specs = [spec for spec in specs if spec.disabled]

        if repeat > 1:
            self.test_runs.sort(key=(lambda test: test.run_number))

        self.success = False

        self.logger.info('Registered tests:')
        for test in self.test_runs:
            self.logger.info(f'- {repr(test)}')
        self.logger.info('')

    def start(self):
        '''Start test execution.'''
        test_queue = list(self.test_runs[::-1])
        running_tests: dict[str, threading.Thread] = {}

        self.progress_bar.create_counters(len(self.test_runs))
        lock = threading.Lock()
        counters = self.progress_bar.Counter

        def thread_callback(test_run: TestRun):
            '''Handle test completion and test retrys.'''
            with lock:
                running_tests.pop(repr(test_run))

                if test_run.result.retry:
                    test_logger = get_logger(repr(test_run), prefix=True)
                    if test_run.result.panic:
                        panic = ''.join(test_run.result.errors)
                        test_logger.info(
                            f'Restarting test, because of {panic}')

                    test_run.result = TestResult(test_repr=repr(test_run),
                                                 test_spec=test_run.spec,
                                                 config=self.config.analyze)

                    self.progress_bar.update_counter(
                        self.progress_bar.Counter.RUNNING, incr=-1)
                    test_queue.append(test_run)

                    return

                counter = counters.FAIL
                if test_run.result.status == TestResult.Status.SUCCESS:
                    counter = counters.SUCCESS

                self.progress_bar.update_counter(counter,
                                                 from_counter=counters.RUNNING)

        def run_test(test_queue: list[TestRun]):
            '''
            Run a single test in a dedicated thread,
            by poping a test run from `test_queue` and passing it to `_run`.
            '''
            with lock:
                test = test_queue.pop()
                self.progress_bar.update_counter(
                    self.progress_bar.Counter.RUNNING)

                thread = threading.Thread(target=_run, args=[
                                          test, self.architecture, self.config,
                                          thread_callback])

                running_tests[repr(test)] = thread
                thread.start()

        # Run all the tests
        for _ in range(self.config.threads):
            if test_queue:
                run_test(test_queue)

        while test_queue or running_tests:
            self.progress_bar.refresh()

            if not test_queue:
                # Probably waiting for a test timeout -> wait longer.
                time.sleep(1)
                continue

            if len(running_tests) < self.config.threads:
                run_test(test_queue)

            time.sleep(0.0001)  # Basically yield
        # Testing finished

        self.success = not any(
            test_run.result.status in (TestResult.Status.FAILED,
                                       TestResult.Status.PANIC)
            for test_run in self.test_runs)

    def create_snapshot(self):
        '''
        Create a Redirect-on-Write snapshot, of the original qcow2 image and
        use `savevm`, to snapshot the vm state.
        '''
        _create_snapshot(self.architecture, QEMU_VMSTATE_TAG, self.config)

    def get_markdown_test_summary(self) -> str:
        '''
        Get a simple summary of all test runs.
        The summary contains table of tests with their run status and
        a summary of all errors that occured.
        '''
        def markdown_table_row(cols: list[str],
                               widths: list[int] = [40, 20]) -> str:
            assert (len(widths) == len(cols))
            res = '|'
            for cell, width in zip(cols, widths):
                padding = width - len(cell) - 2
                if padding < 0:
                    raise ValueError(f'\"{cell}\" is to long '
                                     'for the table width')
                res += f" {cell}{' '*padding}|"
            return res + '\n'

        def markdown_table_delim(widths: list[int] = [40, 20]):
            res = '|'
            for width in widths:
                res += f" {'-'*(width-3)} |"
            return res + '\n'

        self.test_runs.sort(key=(lambda test: repr(test)))
        self.test_runs.sort(key=(lambda test: test.result.status.name))

        summary = ''
        summary += markdown_table_row(['Test run', 'Result'])
        summary += markdown_table_delim()

        for spec in self.disabled_specs:
            summary += markdown_table_row([spec.test_name,
                                           TestResult.Status.DISABLED.name])

        for run in self.test_runs:
            summary += markdown_table_row([repr(run),
                                          run.result.status.name])

        if not self.success:
            failed_runs = (run for run in self.test_runs
                           if run.result.status in (TestResult.Status.FAILED,
                                                    TestResult.Status.PANIC))

            summary += '\n\n'
            summary += '## Errors\n\n'

            for run in failed_runs:
                summary += f'### {repr(run)} - {run.tmp_dir}/out.log\n\n'
                for error in run.result.errors:
                    error = f'{error.strip()}\n'
                    if '```' in error:
                        summary += error
                    else:
                        summary += f'- {error}'
                summary += '\n'

        with open(f'{SWEB_BUILD_DIR}/tortillas_summary.md',
                  'w') as summary_file:
            summary_file.write(summary)

        return summary


def _create_snapshot(architecture: str, label: str, config: TortillasConfig):
    log = get_logger('Create snapshot', prefix=True)

    log.info('Booting SWEB')
    return_reg = 'RAX'
    if architecture == 'x86_32':
        return_reg = 'EAX'

    tmp_dir = f'{TEST_RUN_DIR}/snapshot'
    _clean_tmp_dir(tmp_dir)

    snapshot_qcow2_path = f'{tmp_dir}/SWEB.qcow2'

    subprocess.run(['qemu-img', 'create', '-f', 'qcow2', '-F', 'qcow2', '-b',
                    f'{SWEB_BUILD_DIR}/SWEB.qcow2',
                    snapshot_qcow2_path],
                   check=True,
                   stdout=subprocess.DEVNULL)

    bootup_error = False
    with QemuInterface(
            tmp_dir=tmp_dir,
            qcow2_path=snapshot_qcow2_path,
            arch=architecture,
            logger=log
    ) as qemu:

        if not qemu.is_alive():
            sys.exit(1)

        log.debug('Waiting for bootup...')

        # Wait for the interrupt, that singals bootup completion
        res = qemu.interrupt_watchdog.wait_until(
            int_num=INT_SYSCALL,
            int_regs={
                return_reg: config.sc_tortillas_bootup
            },
            timeout=config.bootup_timeout_secs
        )

        if res in (InterruptWatchdog.Status.TIMEOUT,
                   InterruptWatchdog.Status.STOPPED):
            log.info('Boot attempt failed, dumping logfile!')
            bootup_error = True

        else:
            log.info('Successful bootup!')
            time.sleep(0.1)
            qemu.monitor_command(f'savevm {label}\n')

    if bootup_error:
        with open(f'{tmp_dir}/out.log', 'r') as log_file:
            log.info(log_file.read())
        sys.exit(1)

    subprocess.run(['cp', snapshot_qcow2_path,
                    f'{TEST_RUN_DIR}/SWEB-snapshot.qcow2'],
                   check=True)


def _run(test: TestRun, architecture: str, config: TortillasConfig,
         callback: Callable[['TestRun'], None] | None = None):
    log = test.logger

    return_reg = 'RAX'
    if architecture == 'x86_32':
        return_reg = 'EAX'

    tmp_dir = test.get_tmp_dir()
    _clean_tmp_dir(tmp_dir)

    log.debug(f'Copying SWEB-snapshot.qcow2 to {tmp_dir}')

    snapshot_path = f'{tmp_dir}/SWEB-snapshot.qcow2'
    subprocess.run(['cp', f'{TEST_RUN_DIR}/SWEB-snapshot.qcow2',
                    snapshot_path], check=True)

    log.debug(
        f'Starting qemu snapshot {QEMU_VMSTATE_TAG} (arch={architecture})')

    with QemuInterface(
            tmp_dir=tmp_dir,
            qcow2_path=snapshot_path,
            arch=architecture,
            logger=log,
            vmstate=QEMU_VMSTATE_TAG
    ) as qemu:

        if not qemu.is_alive():
            test.result.retry = True
            if callback:
                callback(test)
            return

        log.info('Starting test execution')
        qemu.sweb_input(f'{test.name}.sweb\n')

        timeout = config.default_test_timeout_secs
        # Overwrite timeout if the TestSpec contains a timeout
        if test.spec.timeout:
            timeout = test.spec.timeout

        # Wait for the interrupt, that signals program completion
        res = qemu.interrupt_watchdog.wait_until(
            int_num=INT_SYSCALL,
            int_regs={
                return_reg: config.sc_tortillas_finished
            },
            timeout=timeout
        )

        if (res == InterruptWatchdog.Status.TIMEOUT
           and not test.spec.expect_timeout):
            test.result.add_execution_error('Test execution timeout')

        if res == InterruptWatchdog.Status.STOPPED:
            test.result.add_execution_error('Test killed, because no more '
                                            'interrupts were comming')

        # Wait a bit for cleanup and debug output to be flushed
        time.sleep(1)

    test.analyze()

    log.info('Done!')
    if callback:
        callback(test)


def _clean_tmp_dir(tmp_dir):
    if pathlib.Path(tmp_dir).is_dir():
        subprocess.run(f'rm {tmp_dir}/*', shell=True)
    else:
        subprocess.run(['mkdir', tmp_dir], check=True)
