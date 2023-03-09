"""This module is used to parse SWEB logs."""

from __future__ import annotations
from pathlib import Path

import re

from .utils import escape_ansi
from .tortillas_config import AnalyzeConfigEntry


class LogParser:
    """Configurable parser for the log output of SWEB."""

    SPLIT_PATTERN = re.compile(
        r"""
        # Debug: https://regex101.com/r/UiFMcy/3
        (                       # Match the 'scope' of the log message
            \[[A-Z_]+\s*\]          # Log identifier. e.g [SYSCALL  ]
        |                           # or
            KERNEL\sPANIC:\s        # KERNEL PANIC:
        )
        (.+?                    # Lazy match everything until
            (?=
                \[[A-Z_]+\s*\]      # Next log identifier
            |                       # or
                KERNEL\sPANIC       # KERNEL PANIC
            |                       # or
                \Z                  # EOF
            )
        )
        """,
        re.DOTALL | re.VERBOSE,
    )

    def __init__(self, log_file_path: Path, config: list[AnalyzeConfigEntry]):
        """
        Set up the parser. The parser will parse the file at `log_file_path`
        with the rules specified by `config`.
        """

        self.log_file_path = log_file_path
        self.config = config

    def parse(self) -> dict[str, list[str]]:
        """
        Open and parse `self.log_file_path` into a dict.
        The dict is keyed by configuration entry names and its values are
        what the pattern of the configuration entry matches in group 1.
        """
        log_data: dict[str, list[str]] = {entry.name: [] for entry in self.config}

        with self.log_file_path.open("rb") as logfile:
            escaped_logs = escape_ansi(logfile.read()).decode()
            for match in self.SPLIT_PATTERN.finditer(escaped_logs):
                debug_log_type = match.group(1).strip("[]: ")

                message = match.group(2)

                for config_entry in self.config:
                    # See if scope matches
                    if config_entry.scope not in ("ALL", debug_log_type):
                        continue

                    scope_match = config_entry.get_compiled_pattern().search(message)
                    if not scope_match:
                        continue

                    log_data[config_entry.name].append(scope_match.group(1))

        return log_data
