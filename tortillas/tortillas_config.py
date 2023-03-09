"""This module handles tortillas configuration."""

from __future__ import annotations
from pathlib import Path

import re
import sys
import dataclasses
import yaml
from logging import Logger
from typing import Any

from .utils import get_logger


@dataclasses.dataclass
class AnalyzeConfigEntry:
    """
    Configuration entry, that specifies how a certain type of log message
    should get parsed and interpreted.
    """

    name: str
    scope: str
    pattern: str
    mode: str

    set_status: str = dataclasses.field(default_factory=str)

    compiled_pattern: re.Pattern | None = None

    def __post_init__(self):
        """Use `re.compile`, to compile the `self.pattern`."""
        self.compiled_pattern = re.compile(self.pattern, re.DOTALL)

    def get_compiled_pattern(self) -> re.Pattern:
        assert self.compiled_pattern
        return self.compiled_pattern


@dataclasses.dataclass(init=False, eq=False)
class TortillasConfig:
    """
    Tortillas configuration class.

    The Constructor will automatically open and
    parse the tortillas config file.

    To add an option, add a member to this class.
    If it has a default value, you make it optional.
    """

    threads: int

    bootup_timeout_secs: int
    default_test_timeout_secs: int

    sc_tortillas_bootup: int
    sc_tortillas_finished: int

    analyze: list[AnalyzeConfigEntry] = dataclasses.field(default_factory=list)

    def __init__(self, config_file_path: Path):
        logger = get_logger("Tortillas config", prefix=True)

        config = _load_tortillas_config(config_file_path, logger)

        # This is manually setting all the attributes, to be able to
        # handle optional fields and construct ConfigEntry objects
        for field in dataclasses.fields(self):
            if field.name not in config.keys():
                if field.default is not dataclasses.MISSING:
                    continue
                logger.error(f'Expected option "{field.name}"')
                sys.exit(1)

            elif field.name == "analyze":
                self.analyze = [AnalyzeConfigEntry(**c) for c in config.pop("analyze")]
            else:
                logger.debug(f"{field.name}: {config[field.name]}")
                setattr(self, field.name, config[field.name])


def _load_tortillas_config(config_file_path: Path, logger: Logger) -> Any:
    with config_file_path.open("r") as yaml_config_file:
        config_raw = yaml_config_file.read()

        try:
            config = yaml.safe_load(config_raw)
        except yaml.YAMLError as exc:
            logger.error(exc)
            sys.exit(1)

    return config
