from __future__ import annotations
from typing import Callable, TextIO

import subprocess
import shlex
import pathlib
import time
import threading

from utils import get_logger, qemu_monitor_command, sweb_input_via_qemu
from constants import TestStatus, TEST_RUN_DIR, SWEB_BUILD_DIR
from interrupt_watchdog import InterruptWatchdog
from tortillas_config import TortillasConfig
from test import Test
from log_parser import LogParser
from progress_bar import ProgressBar


def run_tests(tests: list[Test], architecture: str, progress_bar: ProgressBar,
              config: TortillasConfig):
    test_queue = [test for test in tests]
    running_tests: dict[str, threading.Thread] = {}

    progress_bar.create_run_tests_counters(len(tests))
    lock = threading.Lock()

    def thread_callback(test: Test):
        with lock:
            running_tests.pop(repr(test))

            if test.result.retry:
                test_logger = get_logger(repr(test), prefix=True)
                if test.result.panic:
                    panic = ''.join(test.result.errors)
                    test_logger.info(f'Restarting test, because of {panic}')

                test.result = TestResult(test.name)
                progress_bar.update_counter(
                        progress_bar.Counter.RUNNING, incr=-1)
                test_queue.append(test)

                return

            counter_type = progress_bar.Counter.FAIL
            if (test.result.status == TestStatus.SUCCESS):
                counter_type = progress_bar.Counter.SUCCESS

            progress_bar.update_counter(counter_type,
                                        progress_bar.Counter.RUNNING)

    def run_test(test_queue: list[Test]):
        with lock:
            test = test_queue.pop()
            progress_bar.update_counter(progress_bar.Counter.RUNNING)

            thread = threading.Thread(target=_run, args=[
                                      test, architecture, config,
                                      thread_callback])

            running_tests[repr(test)] = thread
            thread.start()

    # Run all the tests
    for _ in range(config.threads):
        if test_queue:
            run_test(test_queue)

    while test_queue or running_tests:
        progress_bar.refresh()

        if not test_queue:
            # Probably waiting for a test timeout -> wait longer.
            time.sleep(1)
            continue

        if len(running_tests) < config.threads:
            run_test(test_queue)

        time.sleep(0.0001)  # Basically yield
    # Testing finished


def popen_qemu(architecture: str, qcow2_path: str, fifos: str, log_file: str,
               vmstate: str | None = None) -> subprocess.Popen:
    if architecture == 'x86_64':
        cmd = (f'qemu-system-x86_64 -m 8M -cpu qemu64 '
               f'-drive file={qcow2_path},index=0,media=disk '
               f'-debugcon file:{log_file} -monitor pipe:{fifos} '
               '-nographic -display none -serial /dev/null')

    elif architecture == 'x86_32':
        cmd = (f'qemu-system-i386 -m 8M -cpu qemu32 '
               f'-drive file={qcow2_path},index=0,media=disk '
               f'-debugcon file:{log_file} -monitor pipe:{fifos} '
               '-nographic -display none -serial /dev/null')

    else:
        log = get_logger('global')
        log.error(
            f'Architecture {architecture} not yet supported in tortillas')
        exit(-1)

    if vmstate:
        cmd += f' -loadvm {vmstate}'

    return subprocess.Popen(shlex.split(cmd),
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL)


def create_snapshot(architecture: str, label: str, config: TortillasConfig):
    log = get_logger('Create snapshot', prefix=True)

    log.info('Booting SWEB')
    return_reg = 'RAX'
    if (architecture == 'x86_32'):
        return_reg = 'EAX'

    tmp_dir = f'{TEST_RUN_DIR}/snapshot'
    if pathlib.Path(tmp_dir).is_dir():
        log.debug('Removing old files')
        subprocess.run(f'rm {tmp_dir}/*', shell=True)
    else:
        log.debug('Creating new tmp directory')
        subprocess.run(['mkdir', tmp_dir], check=True)

    log.debug('Creating pipes for qemu IO')
    subprocess.run(['mkfifo', '-m', 'a=rw', f'{tmp_dir}/qemu.in'],
                   check=True)
    subprocess.run(['mkfifo', '-m', 'a=rw', f'{tmp_dir}/qemu.out'],
                   check=True)

    subprocess.run(['qemu-img', 'create', '-f', 'qcow2', '-F', 'qcow2', '-b',
                    f'{SWEB_BUILD_DIR}/SWEB.qcow2',
                    f'{tmp_dir}/SWEB.qcow2'],
                   check=True,
                   stdout=subprocess.DEVNULL)

    log.debug(f'Starting qemu (arch={architecture})')
    qemu_process = popen_qemu(architecture,
                              qcow2_path=f'{tmp_dir}/SWEB.qcow2',
                              fifos=f'{tmp_dir}/qemu',
                              log_file=f'{tmp_dir}/out.log')

    if qemu_process.poll():
        log.error('Qemu_process not alive any more!')
        exit(-1)

    with open(f'{tmp_dir}/qemu.in', 'w') as qemu_input:
        interrupt_watchdog = InterruptWatchdog(tmp_dir, log)
        interrupt_watchdog.start(qemu_input)

        log.debug('Waiting for bootup...')

        # Wait for the interrupt, that singals bootup completion
        res = interrupt_watchdog.wait_until(int_num='80',
                                            int_regs={
                                                return_reg:
                                                    config.sc_tortillas_bootup
                                            },
                                            timeout=config.bootup_timeout_secs)

        if 'timeout' in res:
            log.error('Bootup timeout!')
            exit(-1)

        log.info('Successful bootup!')

        interrupt_watchdog.stop(qemu_input)
        interrupt_watchdog.clean()

        time.sleep(0.1)

        qemu_monitor_command(f'savevm {label}\n', file=qemu_input)
        qemu_monitor_command('quit\n', file=qemu_input)

        qemu_process.wait()

    subprocess.run(['cp', f'{tmp_dir}/SWEB.qcow2',
                          f'{TEST_RUN_DIR}/SWEB-snapshot.qcow2'], check=True)


def _run(test: Test, architecture: str, config: TortillasConfig,
        callback: Callable[['Test'], None] | None = None):
    log = test.logger

    tmp_dir = test.get_tmp_dir()

    return_reg = 'RAX'
    if (architecture == 'x86_32'):
        return_reg = 'EAX'

    if pathlib.Path(tmp_dir).is_dir():
        log.debug('Removing old files')
        subprocess.run(f'rm {tmp_dir}/*', shell=True)
    else:
        log.debug('Creating new tmp directory')
        subprocess.run(['mkdir', tmp_dir], check=True)

    log.debug('Creating pipes for qemu IO')
    subprocess.run(['mkfifo', '-m', 'a=rw', f'{tmp_dir}/qemu.in'],
                   check=True)
    subprocess.run(['mkfifo', '-m', 'a=rw', f'{tmp_dir}/qemu.out'],
                   check=True)

    log.debug(f'Copying SWEB.qcow2 to {tmp_dir}')

    snapshot_path = f'{tmp_dir}/SWEB-snapshot.qcow2'
    subprocess.run(['cp', f'{TEST_RUN_DIR}/SWEB-snapshot.qcow2',
                    snapshot_path], check=True)

    log.debug(
        f'Starting qemu snapshot {TEST_RUN_DIR} (arch={architecture})')
    qemu_process = popen_qemu(architecture,
                              qcow2_path=snapshot_path,
                              fifos=f'{tmp_dir}/qemu',
                              log_file=f'{tmp_dir}/out.log',
                              vmstate=TEST_RUN_DIR)

    if qemu_process.poll():
        log.error('Qemu_process not alive any more!')
        test.result.retry = True
        if callback:
            callback(test)
        return

    with open(f'{tmp_dir}/qemu.in', 'w') as qemu_input:
        interrupt_watchdog = InterruptWatchdog(tmp_dir, test.logger)
        interrupt_watchdog.start(qemu_input)

        # run_pra_test_selector(qemu_input,
        #                     interrupt_watchdog, return_reg)

        log.info('Starting test execution')
        sweb_input_via_qemu(f'{test.name}.sweb\n', file=qemu_input)

        timeout = config.default_test_timeout_secs
        # Overwrite timeout if in test config
        if test.config.timeout:
            timeout = test.config.timeout

        # Wait for the interrupt, that signals program completion
        res = interrupt_watchdog.wait_until(int_num='80',
                                            int_regs={
                                                return_reg:
                                                    config.sc_tortillas_finished
                                            },
                                            timeout=timeout)

        if 'timeout' in res and not test.config.expect_timeout:
            log.info('Test execution timeout')
            test.result.add_execution_error('Test execution timeout')

        if 'stopped' in res:
            log.info('Interrupts stopped... Panic?')
            test.result.add_execution_error('Test killed, because no more '
                                            'interrupts were comming')

        interrupt_watchdog.stop(qemu_input)

        # Wait a bit for cleanup and debug output to be flushed
        time.sleep(1)

        log.debug('Quitting')
        qemu_monitor_command('quit\n', file=qemu_input)

        qemu_process.wait()

    parser = LogParser(test, config)
    parser.parse()

    test.result.analyze(parser.log_data)

    log.info('Done!')
    if callback:
        callback(test)


def run_pra_test_selector(test: Test, qemu_input: TextIO,
                          interrupt_watchdog: InterruptWatchdog,
                          return_reg: str, config: TortillasConfig
                          ):

    if not test.config.pra_selector_programm:
        return

    test.logger.info('Running PRA selector')

    sweb_input_via_qemu(f'{test.pra_selector_programm}.sweb\n',
                        file=qemu_input)

    # Wait for the interrupt, that signals program completion
    interrupt_watchdog.wait_until(int_num='80',
                                  int_regs={
                                      return_reg: config.sc_tortillas_finished
                                  },
                                  timeout=config.default_test_timeout_secs)

    interrupt_watchdog.clean()
