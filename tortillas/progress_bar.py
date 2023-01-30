from __future__ import annotations
from enum import Enum

from utils import get_logger


class ProgressBar:
    class Counter(Enum):
        RUNNING = 1
        SUCCESS = 2
        FAIL = 3

    def __init__(self, no_progress_bar: bool = False):
        self.no_bar = no_progress_bar
        if no_progress_bar:
            return

        try:
            import enlighten
        except ImportError:
            self.no_bar = True
            get_logger('default').info(
                'Consider installing \'enlighten\' for a fancy progress bar\n'
                '   pip3 install enlighten\n')
            return

        self.progress_manager = enlighten.get_manager()
        self.justify_center = enlighten.Justify.CENTER
        self.counters = {}
        self.create_main_status_bar()

    def __del__(self):
        if self.no_bar:
            return

        self.progress_manager.stop()

    def refresh(self):
        if self.no_bar:
            return

        self.status_bar.refresh()

    def create_main_status_bar(self):
        if self.no_bar:
            return

        self.status_bar = self.progress_manager.status_bar(
            status_format='Tortillas{fill}{status}{fill}{elapsed}',
            color='bold_black_on_white',
            justify=self.justify_center,
            autorefresh=True,
            status='Gathering tests',
            min_delta=1
        )

    def update_main_status(self, status: str):
        if self.no_bar:
            return

        self.status_bar.update(status=status, force=True)

    def create_run_tests_counters(self, total: int):
        if self.no_bar:
            return

        term = self.progress_manager.term
        bar_format = '{desc}{desc_pad} {count_00:d}/{total:d}|{bar}| ' + \
                     'R:' + term.blue('{count_0:{len_total}d}') + ' ' + \
                     'S:' + term.green('{count_1:{len_total}d}') + ' ' + \
                     'F:' + term.red('{count_2:{len_total}d}') + ' '

        counter = self.progress_manager.counter(total=total,
                                                bar_format=bar_format,
                                                desc='Completed',
                                                unit='tests',
                                                color='blue',
                                                count=0,
                                                leave=False,
                                                autorefresh=True)

        self.counters[self.Counter.RUNNING] = counter
        self.counters[self.Counter.SUCCESS] = counter.add_subcounter('green')
        self.counters[self.Counter.FAIL] = counter.add_subcounter('red')

        counter.refresh()

    def update_counter(self, counter: ProgressBar.Counter,
                       from_counter: ProgressBar.Counter | None = None,
                       incr=1):
        if self.no_bar:
            return

        if counter not in self.Counter:
            return

        if from_counter and from_counter in self.Counter:
            self.counters[counter].update_from(
                self.counters[from_counter], incr=incr)
            return

        self.counters[counter].update(incr=incr)
