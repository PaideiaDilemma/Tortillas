#!/usr/bin/env python3
'''Parse arguments, make a qemu snapshot of SWEB and run applicable tests.'''

from __future__ import annotations
import argparse
import logging
import os
import sys
import threading

from utils import get_logger
from constants import TestStatus, SWEB_BUILD_DIR, TEST_RUN_DIR, QEMU_VMSTATE_TAG
from test_runner import (create_snapshot, run_tests, get_tests_from_specs,
                         get_markdown_test_summary)
from test_specification import get_test_specs, filter_test_specs
from tortillas_config import TortillasConfig
from progress_bar import ProgressBar


# On exception, exit the program
def _exception_hook(args):
    log = get_logger('global')
    log.error("XO", exc_info=args)
    sys.exit(-1)


# Set the exception hook for all threads
threading.excepthook = _exception_hook


def _build_sweb(setup: bool, progress_bar: ProgressBar):
    if setup:
        progress_bar.update_main_status('Setting up SWEB build')
        # This command is equivalent to setup_cmake.sh
        os.system(f'cmake -B\"{SWEB_BUILD_DIR}\" -H.')

    if os.system(f'cmake --build {SWEB_BUILD_DIR}') != 0:
        sys.exit(-1)
    print()


def main():
    log = get_logger('global')

    parser = argparse.ArgumentParser()
    parser.add_argument('--arch',
                        help='Set the architecture to build for e.g. x86_64',
                        default='x86_64', type=str)

    parser.add_argument('-g', '--test-glob',
                        help='Identifier of testcases in the test source dir,'
                             ' e.g. -b test_pthread (tests test_pthread*.c)',
                        default='')

    parser.add_argument('-c', '--category', type=str, nargs='*',
                        help='Category or a list of categories to test')

    parser.add_argument('-t', '--tag', type=str, nargs='*',
                        help='tag or list of tags to test')

    parser.add_argument('-r', '--repeat',
                        help='Run the specified tests mutiple times.'
                             'e.g. -r 2 will run all tests 2 times',
                        default=1, type=int)

    parser.add_argument('-a', '--skip-setup',
                        action='store_true',
                        help='If set, skip the build setup')

    parser.add_argument('-s', '--skip-build',
                        action='store_true',
                        help='If set, skip building sweb')

    parser.add_argument('--no-progress',
                        action='store_true',
                        help='Turn of the progress bar')

    args = parser.parse_args()

    sweb_src_folder = os.getcwd()

    progress_bar = ProgressBar(args.no_progress)
    log.info('Starting tortillas© test system\n')

    config = TortillasConfig()

    all_specs = get_test_specs(sweb_src_folder, args.test_glob)
    selected_specs = filter_test_specs(all_specs, args.category, args.tag)
    disabled_specs = [spec for spec in selected_specs if spec.disabled]

    if len(selected_specs) == 0:
        log.error('No tests were found')
        sys.exit(-1)

    tests = get_tests_from_specs(selected_specs, args.repeat, config)

    log.info('Registered tests:')
    for test in tests:
        log.info(f'- {repr(test)}')
    log.info('')

    if not args.skip_build:
        _build_sweb(not args.skip_setup, progress_bar)

    if not os.path.exists(TEST_RUN_DIR):
        os.mkdir(TEST_RUN_DIR)

    progress_bar.update_main_status('Creating snapshot')
    create_snapshot(args.arch, QEMU_VMSTATE_TAG, config)

    progress_bar.update_main_status('Running tests')
    run_tests(tests, args.arch, progress_bar, config)

    success = not any(
            test.result.status in (TestStatus.FAILED, TestStatus.PANIC)
            for test in tests)

    if not success:
        log.error('Tortillas has failed!')

    log.info('Completed tortillas© test system\n')

    summary = get_markdown_test_summary(tests, disabled_specs, success)

    log.info('')
    log.info(summary)

    logging.shutdown()
    sys.exit(not success)


if __name__ == "__main__":
    main()
