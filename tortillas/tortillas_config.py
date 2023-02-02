'''This module handles tortillas configuration.'''

from __future__ import annotations

import re
import sys
import dataclasses
import yaml

from utils import get_logger
from constants import TORTILLAS_CONFIG_PATH


@dataclasses.dataclass
class ParseConfigEntry:
    '''
    Configuration of the log_parser.
    '''

    name: str
    scope: str
    pattern: str

    pattern_compiled: re.Pattern | None = None

    def compile_pattern(self) -> ParseConfigEntry:
        '''Use `re.compile`, to compile the `self.pattern`.'''
        self.pattern_compiled = re.compile(self.pattern, re.DOTALL)
        return self


@dataclasses.dataclass
class AnalyzeConfigEntry:
    '''
    Configuration for analyzing log data.
    '''

    name: str
    mode: str
    status: str = dataclasses.field(default_factory=str)


@dataclasses.dataclass(eq=False)
class TortillasConfig:
    '''
    Tortillas configuration class.

    The Constructor will automatically open and
    parse the tortillas config file.

    To add an option, add a member to this class.
    If it has no default value, it will be required, otherwise optional.
    '''

    threads: int

    bootup_timeout_secs: int
    default_test_timeout_secs: int

    sc_tortillas_bootup: int
    sc_tortillas_finished: int

    parse: list[ParseConfigEntry] = dataclasses.field(default_factory=list)
    analyze: list[AnalyzeConfigEntry] = dataclasses.field(default_factory=list)

    def __init__(self):
        self.logger = get_logger('Tortillas yaml config', prefix=True)
        with open(TORTILLAS_CONFIG_PATH, 'r') as yaml_config_file:
            config_raw = yaml_config_file.read()

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
