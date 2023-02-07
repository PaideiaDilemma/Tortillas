'''
This module provides functionality, to create and communicate with a
qemu process.
'''

from __future__ import annotations
from typing import TextIO

import os
import sys
import time
import shlex
import subprocess
from enum import Enum

from utils import get_logger


class QemuInterface():
    '''
    Withable class, that creates a qemu process and named pipes to communicate
    with that process.
    '''

    def __init__(self, tmp_dir: str, qcow2_path: str, arch: str,
                 vmstate: str | None = None,
                 interrupts: bool = True):
        self.logger = get_logger(f'QemuInterface {tmp_dir}')

        self.arch = arch
        self.vmstate = vmstate
        self.interrupts = interrupts

        self.qcow2_path = qcow2_path
        self.tmp_dir = tmp_dir
        self.fifos = f'{tmp_dir}/qemu'
        self.log_file = f'{tmp_dir}/out.log'

        self.interrupt_watchdog: InterruptWatchdog
        self.process: subprocess.Popen
        self.input: TextIO

    def __enter__(self):
        self.logger.debug('Creating pipes for qemu IO')

        # subprocess.run(['mkfifo', '-m', 'a=rw', f'{self.fifos}.in'],
        #               check=True)
        # subprocess.run(['mkfifo', '-m', 'a=rw', f'{self.fifos}.out'],
        #               check=True)

        os.mkfifo(f'{self.fifos}.in')
        os.mkfifo(f'{self.fifos}.out')

        self.logger.debug(f'Starting qemu (arch={self.arch})')

        self.process = self._popen_qemu()
        self.input = open(f'{self.fifos}.in', 'w', encoding='utf-8')

        if self.interrupts:
            self.interrupt_watchdog = InterruptWatchdog(self.tmp_dir, self)
            self.interrupt_watchdog.start()

        return self

    def __exit__(self, exc_type, exc_value, traceback):

        if self.interrupts:
            self.interrupt_watchdog.stop()

        if self.is_alive():
            self.logger.debug('Quitting')
            self.monitor_command('quit\n')

        self.input.close()

        self.process.wait()

        os.remove(f'{self.fifos}.in')
        os.remove(f'{self.fifos}.out')

        if exc_type is not None:
            self.logger.error('Error while running tests',
                              exc_info=(exc_type, exc_value, traceback))

    def _popen_qemu(self) -> subprocess.Popen:
        if self.arch in ('x86_64', 'x86/64'):
            cmd = (f'qemu-system-x86_64 -m 8M -cpu qemu64 '
                   f'-drive file={self.qcow2_path},index=0,media=disk '
                   f'-debugcon file:{self.log_file} '
                   f'-monitor pipe:{self.fifos} '
                   '-nographic -display none -serial /dev/null')

        elif self.arch in ('x86_32', 'x86/32'):
            cmd = (f'qemu-system-i386 -m 8M -cpu qemu32 '
                   f'-drive file={self.qcow2_path},index=0,media=disk '
                   f'-debugcon file:{self.log_file} '
                   f'-monitor pipe:{self.fifos} '
                   '-nographic -display none -serial /dev/null')

        else:
            raise NotImplementedError(
                    f'Architecture {self.arch} not yet supported (yet)')

        if self.vmstate:
            cmd += f' -loadvm {self.vmstate}'

        return subprocess.Popen(shlex.split(cmd),
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL)

    def is_alive(self) -> bool:
        '''Return, whether the qemu process is running.'''
        if not self.input or self.process.poll():
            self.logger.error('Qemu_process not alive any more!')
            return False
        return True

    def monitor_command(self, command: str):
        '''
        Send a qemu monitor command.
        See https://www.qemu.org/docs/master/system/monitor.html
        '''
        written_n = self.input.write(command)
        self.input.flush()
        # I ran into some problems without this sleep...
        # Somtimes got "tesT-pthread.." instead of "test_pthread"
        time.sleep(0.2)
        if len(command) != written_n:
            self.logger.error(
                f'Tried to send {len(command)} bytes to input pipe. '
                f'Actually send: {written_n}'
            )

    def sweb_input(self, string: str):
        '''Input to sweb via qemu sendkey.'''
        keymap = {'\n': 'kp_enter', ' ': 'spc', '.': 'dot',
                  '_': 'shift-minus', '-': 'minus', '/': 'slash'}
        for char in string:
            command = ''
            if char in keymap:
                command = f'sendkey {keymap[char]} 100\n'
            elif char.isupper():
                command = f'sendkey shift-{char.lower()} 100\n'
            else:
                command = f'sendkey {char} 100\n'

            self.monitor_command(command)


class InterruptWatchdog:
    '''
    Use qemu interrupt logging, to wait for specfic events and
    detect kernel panics.

    This class parses the ouput of the qemu monitor "log int" command.
    One can wait for an interrupt, by passing an interrupt number and
    a set of registers to the `wait_until` member function.

    Note, that interrupt logs contain some interresting metadata, that one
    could collect in here.
    '''

    class Status(Enum):
        '''Status of the interrupt watchdog.'''
        OK = 1
        TIMEOUT = 2
        STOPPED = 3

    def __init__(self, tmp_dir: str, qemu_interface: QemuInterface):
        self.interrupt_logfile = f'{tmp_dir}/int.log'
        self.logger = qemu_interface.logger

        self.qemu_interface = qemu_interface

        self.sleep_time = 0.5
        self.file_pos = 0

    def start(self):
        '''Start logging interrupts.'''
        self.clean()
        self.qemu_interface.monitor_command(
                f'logfile {self.interrupt_logfile}\n')
        self.qemu_interface.monitor_command('log int\n')

    def clean(self):
        '''Clear/Touch the interrupt logfile.'''
        open(self.interrupt_logfile, 'w').close()  # touch int.log

    def stop(self):
        '''Stop logging interrupts and remove the logfile.'''
        self.qemu_interface.monitor_command('log none\n')
        os.remove(self.interrupt_logfile)

    def wait_until(self, int_num: str, int_regs: dict[str, int],
                   timeout: int) -> Status:
        '''
        Loop until we find an interrupt, that matches `int_num` and `int_regs`.
        If `int_regs` is empty it will match the first interrupt with `int_num`.
        '''
        max_iterations = int(timeout / self.sleep_time)

        iterations_file_unchanged = 0

        for _ in range(max_iterations):
            previous_position = self.file_pos
            time.sleep(self.sleep_time)

            with open(self.interrupt_logfile, 'r') as logfile:
                logfile.seek(self.file_pos)
                lines = logfile.readlines()
                interrupt = self.search_interrupt(int_num, int_regs, lines)
                if interrupt:
                    return self.Status.OK
                self.file_pos = logfile.tell()

            if self.file_pos == previous_position:
                if iterations_file_unchanged > 10:
                    self.logger.error('Interrupts stopped... Panic?')
                    return self.Status.STOPPED

                iterations_file_unchanged += 1
            else:
                iterations_file_unchanged = 0

        self.logger.error(f'Timeout! {int_num}: {int_regs}')

        return self.Status.TIMEOUT

    @staticmethod
    def parse_interrupt(interrupt: str) -> dict[str, int]:
        '''
        This function parses the registers of an interrupt into a dict,
        where the key is the name of the register and
        the value is the register state.

        Example Interrupt:
        RAX=0000000000000004 RBX=0000000000000001 RCX=00007ffffffffd50...
             ...
        CR0=80010013 CR2=0000000008008000 CR3=00000000003f0000 CR4=00000220
             ...
        CCS=0000000000000020 CCD=00007ffffffffd20 CCO=SUBQ
        EFER=0000000000000d00

        The above will become {'RAX': 0x4, 'RBX': 0x1, ...}.
        '''
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

    @staticmethod
    def match_registers(search_regs: dict[str, int],
                        int_regs: dict[str, int]) -> bool:
        '''
        Check whether all register values in search_regs match with
        the values in int_regs.
        Registers, that are not present in search_regs will be ignored.
        '''
        for reg, val in int_regs.items():
            if reg not in search_regs.keys():
                continue
            if search_regs[reg] != val:
                return False
        return True

    @staticmethod
    def search_interrupt(int_num: int, search_regs: dict[str, int],
                         lines: list[str]) -> dict[str, int] | None:
        '''Search for a specific interrupt in `lines`.'''
        for index, line in enumerate(lines):
            if f'v={int_num}' not in line:
                continue

            # A block is usually 20 lines long.
            # If that is not the case,
            # we search for the next inerrupt in a range from 1-30
            block_size = 0
            for block_size in [21] + list(range(1, 30)):
                if (index + block_size + 1 >= len(lines) or
                        'v=' in lines[index + block_size]):
                    break

            interrupt = ''.join((line.strip('\n') + ' '
                                 for line in lines[index + 1:
                                                   index + block_size]))

            registers = InterruptWatchdog.parse_interrupt(interrupt)
            if InterruptWatchdog.match_registers(search_regs, registers):
                return registers
        return None
