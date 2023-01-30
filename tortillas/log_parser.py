from __future__ import annotations

import re
import logging

from utils import escape_ansi
from tortillas_config import TortillasConfig, ParseConfigEntry


class LogParser:
    def __init__(self, log_file_path: str, logger: logging.Logger,
                 config: TortillasConfig):

        self.log_file_path = log_file_path
        self.logger = logger

        self.config: list[ParseConfigEntry] = config.parse

        self.split_by_pattern = re.compile(
                r'\[([A-Z]+ *)\]((?s).+?(?=\[[A-Z]+ *\]|\Z))', re.DOTALL)

        self.log_data: dict[str, list[str]] = {entry.name: []
                                               for entry in self.config}

    def parse(self):
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

                    self.log_data[config_entry.name].append(match.group(1))
