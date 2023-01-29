from __future__ import annotations
from typing import Optional

import re
import yaml
import sys
import dataclasses

from utils import get_logger
from constants import TORTILLAS_CONFIG_PATH


@dataclasses.dataclass(eq=False)
class TortillasConfig:
    threads: int

    bootup_timeout_secs: int
    default_test_timeout_secs: int

    sc_tortillas_bootup: int
    sc_tortillas_finished: int

    parse: list[ParseConfigEntry] = dataclasses.field(default_factory=list)
    analyze: list[AnalyzeConfigEntry] = dataclasses.field(default_factory=list)

    def __init__(self):
        self.logger = get_logger('Tortillas config (config.yml)', prefix=True)
        with open(TORTILLAS_CONFIG_PATH, 'r') as f:
            config_raw = f.read()

            try:
                config = yaml.safe_load(config_raw)
            except yaml.YAMLError as exc:
                self.logger.error(exc)
                sys.exit(-1)

            for field in dataclasses.fields(self):
                if field.name not in config.keys():
                    if field.default is not dataclasses.MISSING:
                        continue
                    self.logger.error(
                        f'Expected option \"{field.name}\"')
                    sys.exit(-1)

                if field.name == 'parse':
                    self.parse = [ParseConfigEntry(**c).compile_pattern()
                                  for c in config.pop('parse')]

                elif field.name == 'analyze':
                    self.analyze = [AnalyzeConfigEntry(**c)
                                    for c in config.pop('analyze')]
                else:
                    self.logger.debug(f'{field.name}: {config[field.name]}')
                    setattr(self, field.name, config[field.name])


@dataclasses.dataclass
class ParseConfigEntry:
    name: str
    scope: str
    pattern: str
    mode: Optional[str] = dataclasses.field(default='default')
    split: Optional[str] = dataclasses.field(default_factory=str)

    pattern_compiled: Optional[re.Pattern] = None

    def compile_pattern(self) -> ParseConfigEntry:
        self.pattern_compiled = re.compile(self.pattern, re.DOTALL)
        return self


@dataclasses.dataclass
class AnalyzeConfigEntry:
    name: str
    mode: str
    status: Optional[str] = dataclasses.field(default_factory=str)
