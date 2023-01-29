from __future__ import annotations
from test import Test

import re

from utils import escape_ansi
from tortillas_config import TortillasConfig, ParseConfigEntry


class LogParser:
    def __init__(self, test: Test, config: TortillasConfig):

        self.log_file_path = test.get_tmp_dir() + '/out.log'
        self.logger = test.logger

        self.config: list[ParseConfigEntry] = config.parse

        self.split_by_pattern = re.compile(r'\[([A-Z]+ *)\]((?s).+?(?=\[[A-Z]+ *\]))', re.DOTALL)

        self.log_data: dict[str, list[str]] = {entry.name: []
                                               for entry in self.config}

    def parse(self):
        self.logger.info('Parsing test output')

        with open(self.log_file_path, 'rb') as f:
            escaped_logs = escape_ansi(f.read()).decode()
            for match in self.split_by_pattern.finditer(escaped_logs):
                debug_log_type = match.group(1).strip()
                message = match.group(2)

                for config_entry in self.config:
                    # See if scope matches
                    if (config_entry.scope != 'ALL' and
                       config_entry.scope != debug_log_type):
                        continue

                    match = config_entry.pattern_compiled.search(message)
                    if not match:
                        continue

                    self.log_data[config_entry.name].append(match.group(1))
