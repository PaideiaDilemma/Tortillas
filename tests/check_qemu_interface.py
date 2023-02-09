import os
import subprocess
from tortillas.qemu_interface import QemuInterface, InterruptWatchdog


def _setup(directory: str):
    assert os.path.exists('/tmp/sweb/SWEB.qcow2')  # Compile sweb??
    if not os.path.exists(f'/tmp/sweb/{directory}'):
        os.mkdir(f'/tmp/sweb/{directory}')
    else:
        subprocess.run(f'rm /tmp/sweb/{directory}/*', shell=True)


def test_waiting_for_bootup():
    _setup('test1')

    with QemuInterface(tmp_dir='/tmp/sweb/test1',
                       qcow2_path='/tmp/sweb/SWEB.qcow2') as qemu:

        res = qemu.interrupt_watchdog.wait_until(int_num=80,
                                                 int_regs={
                                                    'RAX': 69420
                                                    },
                                                 timeout=10)

        assert res not in (InterruptWatchdog.Status.TIMEOUT,
                           InterruptWatchdog.Status.STOPPED)


def test_timeout():
    _setup('test2')

    with QemuInterface(tmp_dir='/tmp/sweb/test2',
                       qcow2_path='/tmp/sweb/SWEB.qcow2') as qemu:

        res = qemu.interrupt_watchdog.wait_until(int_num=80,
                                                 int_regs={
                                                    'RAX': 11111
                                                    },
                                                 timeout=10)

        assert res == InterruptWatchdog.Status.TIMEOUT


def test_run_mult():
    _setup('test3')

    with QemuInterface(tmp_dir='/tmp/sweb/test3',
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
