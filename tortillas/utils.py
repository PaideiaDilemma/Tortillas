from __future__ import annotations

import logging
import re

from constants import LOG_LEVEL


def get_logger(name: str, prefix: bool = False) -> logging.Logger:
    log = logging.getLogger(name)
    if not log.handlers:
        log.propagate = False
        console_handler = logging.StreamHandler()
        log.addHandler(console_handler)
        format = '%(name)s: %(message)s' if prefix else '%(message)s'
        console_handler.setFormatter(logging.Formatter(format))
    log.setLevel(LOG_LEVEL)
    return log


def escape_ansi(line: bytes) -> bytes:
    '''
    We need to handle ansi rescape sequesces in the qemu serial output.
    Otherwise, there is no guarantie to match a specific string.

    I took the regex from this post: https://stackoverflow.com/a/14693789
    THis matches 7-bit C1 ANSI sequences but not 8-bit ones!!
    '''
    ansi_re = re.compile(rb'''
        \x1B  # ESC
        (?:   # 7-bit C1 Fe (except CSI)
            [@-Z\\-_]
        |     # or [ for CSI, followed by a control sequence
            \[
            [0-?]*  # Parameter bytes
            [ -/]*  # Intermediate bytes
            [@-~]   # Final byte
        )
    ''', re.VERBOSE)
    return ansi_re.sub(b'', line)
