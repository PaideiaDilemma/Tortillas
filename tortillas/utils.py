from __future__ import annotations
from typing import TextIO

import logging
import time
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


def qemu_monitor_command(data: list[str] | str, file: TextIO):
    log = get_logger('global')
    if (not isinstance(data, list)):
        data = [data]

    for line in data:
        written_n = file.write(line)
        file.flush()
        # I ran into some problems without this sleep...
        # Somtimes got "tesT-pthread.." instead of "test_pthread"
        time.sleep(0.2)
        if (len(line) != written_n):
            log.error(f'Tried to send {len(data)} bytes to input pipe. '
                      f'Actually send: {written_n}')


def sweb_input_via_qemu(string: str, file: TextIO):
    data = []
    keymap = {'\n': 'kp_enter', ' ': 'spc', '.': 'dot',
              '_': 'shift-minus', '-': 'minus', '/': 'slash'}
    for char in string:
        if char in keymap:
            data.append(f'sendkey {keymap[char]} 100\n')
        elif char.isupper():
            data.append(f'sendkey shift-{char.lower()} 100\n')
        else:
            data.append(f'sendkey {char} 100\n')

    qemu_monitor_command(data, file)


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
