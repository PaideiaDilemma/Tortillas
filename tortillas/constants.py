"""This module exclusively contains constants."""

import logging
from pathlib import Path

LOG_LEVEL = logging.INFO

SWEB_BUILD_DIR = Path("/tmp/sweb")
TEST_RUN_DIR = Path(f"{SWEB_BUILD_DIR}/tortillas")

TEST_FOLDER_PATH = "userspace/tests"
QEMU_VMSTATE_TAG = "tortillas"

TORTILLAS_EXPECT_PREFIX = "TORTILLAS EXPECT: "
INT_SYSCALL = 80
