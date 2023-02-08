'''This module is used to parse SWEB logs.'''

from __future__ import annotations

import re
import logging

from .utils import escape_ansi
from .tortillas_config import ParseConfigEntry


class LogParser:
    '''Configurable parser for the log output of SWEB.'''

    def __init__(self, log_file_path: str, logger: logging.Logger,
                 config: list[ParseConfigEntry]):
        '''
        Setup the parser. The parser will parse the file at `log_file_path`
        with the rules specified by `config`.
        '''

        self.log_file_path = log_file_path
        self.logger = logger

        self.config: list[ParseConfigEntry] = config

        self.split_by_pattern = re.compile(
                r'\[([A-Z]+ *)\]((?s).+?(?=\[[A-Z]+ *\]|\Z))', re.DOTALL)

    def parse(self) -> dict[str, list[str]]:
        '''
        Open and parse `self.log_file_path` into a dict.
        The dict is keyed by configuration entry names and its values are
        what the pattern of the configuration entry matches in group 1.
        '''
        log_data: dict[str, list[str]] = {entry.name: []
                                          for entry in self.config}
        self.logger.info('Parsing test output')

        with open(self.log_file_path, 'rb') as logfile:
            escaped_logs = escape_ansi(logfile.read()).decode()
            for match in self.split_by_pattern.finditer(escaped_logs):
                debug_log_type = match.group(1).strip()
                message = match.group(2)

                for config_entry in self.config:
                    # See if scope matches
                    if config_entry.scope not in ('ALL', debug_log_type):
                        continue

                    match = config_entry.pattern_compiled.search(message)
                    if not match:
                        continue

                    log_data[config_entry.name].append(match.group(1))

        return log_data
