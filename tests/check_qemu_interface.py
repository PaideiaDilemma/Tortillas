import subprocess
from pathlib import Path
from tortillas.qemu_interface import QemuInterface, InterruptWatchdog

IMAGE_PATH = Path("/tmp/sweb/SWEB.qcow2")
TEST_RUN_DIR = Path("/tmp/sweb/test")


def _setup():
    assert IMAGE_PATH.exists()
    if not TEST_RUN_DIR.is_dir():
        TEST_RUN_DIR.mkdir()
    else:
        subprocess.run(f"rm {TEST_RUN_DIR}/*", shell=True)


def test_waiting_for_bootup():
    _setup()

    with QemuInterface(
        tmp_dir=Path("/tmp/sweb/test"), qcow2_path=Path("/tmp/sweb/SWEB.qcow2")
    ) as qemu:
        res = qemu.interrupt_watchdog.wait_until(
            int_num=80, int_regs={"RAX": 1337}, timeout=10
        )

        assert res not in (
            InterruptWatchdog.Status.TIMEOUT,
            InterruptWatchdog.Status.STOPPED,
        )


def test_timeout():
    _setup()

    with QemuInterface(
        tmp_dir=Path("/tmp/sweb/test"), qcow2_path=Path("/tmp/sweb/SWEB.qcow2")
    ) as qemu:
        res = qemu.interrupt_watchdog.wait_until(
            int_num=80, int_regs={"RAX": 11111}, timeout=10
        )

        assert res == InterruptWatchdog.Status.TIMEOUT


def test_run_mult():
    _setup()

    with QemuInterface(
        tmp_dir=Path("/tmp/sweb/test"), qcow2_path=Path("/tmp/sweb/SWEB.qcow2")
    ) as qemu:
        res = qemu.interrupt_watchdog.wait_until(
            int_num=80, int_regs={"RAX": 1337}, timeout=10
        )

        assert res not in (
            InterruptWatchdog.Status.TIMEOUT,
            InterruptWatchdog.Status.STOPPED,
        )

        qemu.sweb_input("mult.sweb\n")

        res = qemu.interrupt_watchdog.wait_until(
            int_num=80, int_regs={"RAX": 1338}, timeout=20
        )

        assert res not in (
            InterruptWatchdog.Status.TIMEOUT,
            InterruptWatchdog.Status.STOPPED,
        )
