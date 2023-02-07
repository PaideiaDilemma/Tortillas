'''This module exclusively contains constants.'''

import logging

LOG_LEVEL = logging.INFO

SWEB_BUILD_DIR = r'/tmp/sweb'
TEST_RUN_DIR = rf'{SWEB_BUILD_DIR}/tortillas'
TEST_FOLDER_PATH = r'userspace/tests'
QEMU_VMSTATE_TAG = 'tortillas'

INT_SYSCALL = 80
