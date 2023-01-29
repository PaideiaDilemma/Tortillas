#!/usr/bin/env python3

# SPDX-FileCopyrightText: © 2022 Leo Moser, Maximilian Seidler
import argparse
import logging
import os
import sys
import pathlib
import threading

from utils import get_logger
from constants import TestStatus, TEST_FOLDER_PATH, TEST_RUN_DIR
from test_runner import create_snapshot, run_tests
from tortillas_config import TortillasConfig
from progress_bar import ProgressBar
from test import Test
from test_config import NoTestConfigFound


# On exception, exit the program
def exception_hook(args):
    log = get_logger('global')
    log.error("XO", exc_info=args)
    os._exit(-1)


# Set the exception hook for all threads
threading.excepthook = exception_hook


def get_tests_to_run(tortillas_config: TortillasConfig, sweb_src_folder: str,
                     test_glob: str, repeat: bool, category: list[str],
                     tag: list[str], **kwargs) -> tuple[list[Test], list[str]]:
    # Register all tests
    file_paths = list(pathlib.Path(
        TEST_FOLDER_PATH).glob(f'{test_glob}*.c'))

    tests: list[Test] = []
    for file_path in file_paths:
        for num in range(repeat):
            try:
                tests.append(Test(file_path.stem, num+1, sweb_src_folder,
                                  tortillas_config))
            except NoTestConfigFound:
                continue

    if category:
        tests = [test for test in tests
                 if test.config.category() in category]

    if tag:
        tests = [test for test in tests
                 if any(tag in test.config.tags() for tag in tag)]

    disabled_tests = [test.name for test in tests if test.config.disabled]
    tests = [test for test in tests if not test.config.disabled]

    tests.sort(key=(lambda test: repr(test)), reverse=True)
    tests.sort(key=(lambda test: test.config.timeout))

    return tests, disabled_tests


def get_markdown_test_summary(tests: list[Test],
                              disabled_tests: list[Test],
                              success: bool) -> str:

    def markdown_table_row(cols, widths=[40, 20]) -> str:
        assert (len(widths) == len(cols))
        res = '|'
        for cell, width in zip(cols, widths):
            padding = width - len(cell) - 2
            if padding < 0:
                raise ValueError(f'\"{cell}\" is to long '
                                 'for the table width')
            res += f" {cell}{' '*padding}|"
        return res + '\n'

    def markdown_table_delim(widths=[40, 20]):
        res = '|'
        for width in widths:
            res += f" {'-'*(width-3)} |"
        return res + '\n'

    tests.sort(key=(lambda test: test.result.status.name))

    summary = ''
    summary += markdown_table_row(['Test run', 'Result'])
    summary += markdown_table_delim()

    for test in disabled_tests:
        summary += markdown_table_row([test, TestStatus.DISABLED.name])

    for test in tests:
        summary += markdown_table_row([repr(test),
                                      test.result.status.name])

    if not success:
        failed_tests = (test for test in tests
                        if test.result.status in
                        [TestStatus.FAILED, TestStatus.PANIC])

        summary += '\n\n'
        summary += '## Errors\n\n'

        for test in failed_tests:
            summary += f'### {repr(test)} - {test.get_tmp_dir()}/out.log\n\n'
            for line in test.result.errors:
                if line[-1] not in ['\n', '\r']:
                    line = f'{line}\n'

                if '=== Begin of backtrace' in line:
                    summary += f'```\n{line}```'
                    continue

                summary += f'- {line}'

    with open('tortillas_summary.md', 'w') as f:
        f.write(summary)

    return summary


def main():
    log = get_logger('global')

    parser = argparse.ArgumentParser()
    parser.add_argument('--arch',
                        help='Set the architecture to build for e.g. x86_64',
                        default='x86_64', type=str)

    parser.add_argument('-g', '--test-glob',
                        help='Identifier of testcases in the test source dir,'
                             ' e.g. -b pthread (tests test_pthread*.c)',
                        default='')

    parser.add_argument('-c', '--category', type=str, nargs='*',
                        help='Category or a list of categories to test')

    parser.add_argument('-t', '--tag', type=str, nargs='*',
                        help='tag or list of tags to test')

    parser.add_argument('-r', '--repeat',
                        help='Run the specified tests mutiple times.'
                             'e.g. -r 2 will run all tests 2 times',
                        default=1, type=int)

    parser.add_argument('-a', '--skip-arch',
                        action='store_true',
                        help='If set, skip architecture build')

    parser.add_argument('-s', '--skip',
                        action='store_true',
                        help='If set, skip build')

    parser.add_argument('--no-progress',
                        action='store_true',
                        help='Turn of the progress bar')

    args = parser.parse_args()

    sweb_src_folder = os.getcwd()

    progress_bar = ProgressBar(args.no_progress)
    log.info('Starting tortillas© test system\n')

    config = TortillasConfig()
    tests, disabled_tests = get_tests_to_run(config, sweb_src_folder,
                                             **vars(args))

    if len(tests) == 0:
        log.error('No tests were found')
        sys.exit(-1)

    log.info('Registered tests:')
    for test in tests:
        log.info('- {}'.format(repr(test)))
    log.info('')

    # Build
    if not args.skip_arch and not args.skip:
        progress_bar.update_main_status('Setting up SWEB build')
        os.system('./setup_cmake.sh')
        os.chdir('/tmp/sweb')
        os.system('echo yes | make {}'.format(args.arch))
    else:
        os.chdir('/tmp/sweb')

    if not args.skip:
        progress_bar.update_main_status('Building SWEB')
        if os.system('make') != 0:
            return -1
        log.info('')

    if not os.path.exists(TEST_RUN_DIR):
        os.mkdir(TEST_RUN_DIR)

    progress_bar.update_main_status('Creating snapshot')
    create_snapshot(args.arch, TEST_RUN_DIR, config)

    progress_bar.update_main_status('Running tests')
    run_tests(tests, args.arch, progress_bar, config)

    success = True
    for test in tests:
        if test.result.status in [TestStatus.FAILED, TestStatus.PANIC]:
            success = False

    if not success:
        log.error('Tortillas has failed!')

    log.info('Completed tortillas© test system\n')

    summary = get_markdown_test_summary(tests, disabled_tests, success)

    log.info('')
    log.info(summary)

    logging.shutdown()
    sys.exit(not success)


if __name__ == "__main__":
    main()
