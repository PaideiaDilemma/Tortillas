from enum import Enum
import logging

LOG_LEVEL = logging.INFO

TEST_FOLDER_PATH = r'userspace/tests'
TORTILLAS_CONFIG_PATH = r'tortillas_config.yml'
QEMU_VMSTATE_TAG = 'tortillas'

INT_SYSCALL = 80


class TestStatus(Enum):
    DISABLED = 1
    SUCCESS = 2
    FAILED = 3
    PANIC = 4
