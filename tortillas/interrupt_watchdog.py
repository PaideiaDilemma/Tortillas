from __future__ import annotations
from typing import TextIO

import logging
import os
import time

from qemu_interface import QemuInterface


class InterruptWatchdog:
    def __init__(self, tmp_dir: str, qemu_interface: QemuInterface,
                 logger: logging.Logger):
        self.interrupt_logfile = f'{tmp_dir}/int.log'
        self.logger = logger

        self.qemu_interface = qemu_interface

        self.sleep_time = 0.5
        self.file_pos = 0

    def start(self):
        self.clean()
        self.qemu_interface.monitor_command(
                f'logfile {self.interrupt_logfile}\n')
        self.qemu_interface.monitor_command('log int\n')

    def stop(self):
        self.qemu_interface.monitor_command('log none\n')
        os.remove(self.interrupt_logfile)

    def clean(self):
        open(self.interrupt_logfile, 'w').close()  # touch int.log

    def wait_until(self, int_num: str, int_regs: dict[str, int],
                   timeout: int) -> dict[str, int]:
        '''
        This function parses the ouput of the qemu monitor "log int" command.
        It parses the registers of an interrupt into a dict, where the key is
        the name of the register and the value is the register state.

        RAX=0000000000000004 RBX=0000000000000001 RCX=00007ffffffffd50...
             ...
        CR0=80010013 CR2=0000000008008000 CR3=00000000003f0000 CR4=00000220
             ...
        CCS=0000000000000020 CCD=00007ffffffffd20 CCO=SUBQ
        EFER=0000000000000d00

        The above wil become {'RAX': 0x4, 'RBX': 0x1, ...}.
        One can then match an interrupt, by passing the interrupt number and
        a set of registers having the same format to this function.
        If interrupt_regs is empty it will match the first interrupt with the
        specified number.
        '''
        max_iterations = int(timeout / self.sleep_time)

        iterations_file_unchanged = 0

        for _ in range(max_iterations):
            previous_position = self.file_pos
            time.sleep(self.sleep_time)

            with open(f'{self.interrupt_logfile}', 'r') as f:
                f.seek(self.file_pos)
                lines = f.readlines()
                interrupt = self.find_interrupt(int_num, int_regs, lines)
                if interrupt:
                    return self.parse_interrupt(interrupt)
                self.file_pos = f.tell()

            if (self.file_pos == previous_position):
                if iterations_file_unchanged > 10:
                    return {'stopped': True}

                iterations_file_unchanged += 1
            else:
                iterations_file_unchanged = 0

        self.logger.error(f'Timeout! {int_num}: {int_regs}')

        return {'timeout': True}

    def parse_interrupt(self, interrupt: str) -> dict[str, int]:
        regs = {}
        for register in interrupt.split(' '):
            if not register or '=' not in register or register[-1] == '=':
                continue
            key, val = register.split('=')[:2]
            if not key or not val:
                continue
            try:
                regs[key] = int(val, 16)
            except ValueError:
                continue
        return regs

    def match_registers(self, int_regs: dict[str, int],
                        interrupt: str) -> bool:
        parsed_interrupt_regs = self.parse_interrupt(interrupt)
        for reg, val in int_regs.items():
            if reg not in parsed_interrupt_regs:
                continue
            if parsed_interrupt_regs[reg] != val:
                return False
        return True

    def find_interrupt(self, int_num: int, int_regs: dict[str, int],
                       lines: list[str]) -> str:
        for idx in range(len(lines)):
            if f'v={int_num}' not in lines[idx]:
                continue

            # A block is usually 20 lines long.
            # If that is not the case,
            # we search for the next inerrupt in a range from 1-30
            block_size = 0
            for block_size in [21] + list(range(1, 30)):
                if (idx + block_size + 1 >= len(lines) or
                        'v=' in lines[idx + block_size]):
                    break

            interrupt = ''.join((line.strip('\n') + ' '
                                 for line in lines[idx+1:idx+block_size]))

            if self.match_registers(int_regs, interrupt):
                return interrupt
        return ''
