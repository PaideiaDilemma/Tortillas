import os
import subprocess
from tortillas.qemu_interface import QemuInterface, InterruptWatchdog


def _setup():
    assert os.path.exists('/tmp/sweb/SWEB.qcow2')  # Compile sweb??
    if not os.path.exists('/tmp/sweb/test'):
        os.mkdir('/tmp/sweb/test')
    else:
        subprocess.run('rm /tmp/sweb/test/*', shell=True)


def test_waiting_for_bootup():
    _setup()

    with QemuInterface(tmp_dir='/tmp/sweb/test',
                       qcow2_path='/tmp/sweb/SWEB.qcow2') as qemu:

        res = qemu.interrupt_watchdog.wait_until(int_num=80,
                                                 int_regs={
                                                    'RAX': 69420
                                                    },
                                                 timeout=10)

        assert res not in (InterruptWatchdog.Status.TIMEOUT,
                           InterruptWatchdog.Status.STOPPED)


def test_timeout():
    _setup()

    with QemuInterface(tmp_dir='/tmp/sweb/test',
                       qcow2_path='/tmp/sweb/SWEB.qcow2') as qemu:

        res = qemu.interrupt_watchdog.wait_until(int_num=80,
                                                 int_regs={
                                                    'RAX': 11111
                                                    },
                                                 timeout=10)

        assert res == InterruptWatchdog.Status.TIMEOUT


def test_run_mult():
    _setup()

    with QemuInterface(tmp_dir='/tmp/sweb/test',
                       qcow2_path='/tmp/sweb/SWEB.qcow2') as qemu:

        res = qemu.interrupt_watchdog.wait_until(int_num=80,
                                                 int_regs={
                                                    'RAX': 69420
                                                    },
                                                 timeout=10)

        assert res not in (InterruptWatchdog.Status.TIMEOUT,
                           InterruptWatchdog.Status.STOPPED)

        qemu.sweb_input('mult.sweb\n')

        res = qemu.interrupt_watchdog.wait_until(int_num=80,
                                                 int_regs={
                                                    'RAX': 42069
                                                    },
                                                 timeout=20)

        assert res not in (InterruptWatchdog.Status.TIMEOUT,
                           InterruptWatchdog.Status.STOPPED)
