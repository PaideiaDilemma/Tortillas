from __future__ import annotations

import os
import time
import shlex
import logging
import subprocess

from utils import get_logger


class QemuInterface():
    def __init__(self, tmp_dir: str, qcow2_path: str, arch: str,
                 logger: logging.Logger, vmstate: str | None = None):
        self.logger = logger

        self.arch = arch
        self.vmstate = vmstate

        self.qcow2_path = qcow2_path
        self.fifos = f'{tmp_dir}/qemu'
        self.log_file = f'{tmp_dir}/out.log'

    def __enter__(self):
        self.logger.debug('Creating pipes for qemu IO')

        #subprocess.run(['mkfifo', '-m', 'a=rw', f'{self.fifos}.in'],
        #               check=True)
        #subprocess.run(['mkfifo', '-m', 'a=rw', f'{self.fifos}.out'],
        #               check=True)

        os.mkfifo(f'{self.fifos}.in')
        os.mkfifo(f'{self.fifos}.out')

        self.logger.debug(f'Starting qemu (arch={self.arch})')

        self.process = self._popen_qemu()
        self.input = open(f'{self.fifos}.in', 'w')

        return self

    def __exit__(self, exc_type, exc_val, bt):
        self.process.wait()

        self.input.close()

        os.remove(f'{self.fifos}.in')
        os.remove(f'{self.fifos}.out')

        if exc_type is not None:
            self.logger.error('Error while running tests',
                              exc_info=(exc_type, exc_val, bt))
            exit(-1)

    def _popen_qemu(self) -> subprocess.Popen:
        if self.arch == 'x86_64':
            cmd = (f'qemu-system-x86_64 -m 8M -cpu qemu64 '
                   f'-drive file={self.qcow2_path},index=0,media=disk '
                   f'-debugcon file:{self.log_file} -monitor pipe:{self.fifos} '
                   '-nographic -display none -serial /dev/null')

        elif self.arch == 'x86_32':
            cmd = (f'qemu-system-i386 -m 8M -cpu qemu32 '
                   f'-drive file={self.qcow2_path},index=0,media=disk '
                   f'-debugcon file:{self.log_file} -monitor pipe:{self.fifos} '
                   '-nographic -display none -serial /dev/null')

        else:
            log = get_logger('global')
            log.error(
                f'Architecture {self.arch} not yet supported in tortillas')
            exit(-1)

        if self.vmstate:
            cmd += f' -loadvm {self.vmstate}'

        return subprocess.Popen(shlex.split(cmd),
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL)

    def is_alive(self) -> bool:
        if not self.input or self.process.poll():
            self.logger.error('Qemu_process not alive any more!')
            return False
        return True

    def monitor_command(self, data: list[str] | str):
        if (not isinstance(data, list)):
            data = [data]

        for line in data:
            written_n = self.input.write(line)
            self.input.flush()
            # I ran into some problems without this sleep...
            # Somtimes got "tesT-pthread.." instead of "test_pthread"
            time.sleep(0.2)
            if (len(line) != written_n):
                self.logger.error(
                          f'Tried to send {len(data)} bytes to input pipe. '
                          f'Actually send: {written_n}'
                        )

    def sweb_input(self, string: str):
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

        self.monitor_command(data)
