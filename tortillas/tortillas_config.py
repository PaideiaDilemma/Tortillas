'''This module handles tortillas configuration.'''

from __future__ import annotations

import re
import sys
import dataclasses
import yaml

from .utils import get_logger


@dataclasses.dataclass
class AnalyzeConfigEntry:
    '''
    Configuration of the log_parser.
    '''

    name: str
    scope: str
    pattern: str

    mode: str = dataclasses.field(default_factory=str)
    status: str = dataclasses.field(default_factory=str)

    pattern_compiled: re.Pattern | None = None

    def compile_pattern(self) -> AnalyzeConfigEntry:
        '''Use `re.compile`, to compile the `self.pattern`.'''
        self.pattern_compiled = re.compile(self.pattern, re.DOTALL)
        return self


@dataclasses.dataclass(init=False, eq=False)
class TortillasConfig:
    '''
    Tortillas configuration class.

    The Constructor will automatically open and
    parse the tortillas config file.

    To add an option, add a member to this class.
    If it has a default value, you make it optional.
    '''

    threads: int

    bootup_timeout_secs: int
    default_test_timeout_secs: int

    sc_tortillas_bootup: int
    sc_tortillas_finished: int

    analyze: list[AnalyzeConfigEntry] = dataclasses.field(default_factory=list)

    def __init__(self, config_file_path: str):
        self.logger = get_logger('Tortillas config', prefix=True)
        with open(config_file_path, 'r') as yaml_config_file:
            config_raw = yaml_config_file.read()

            try:
                config = yaml.safe_load(config_raw)
            except yaml.YAMLError as exc:
                self.logger.error(exc)
                sys.exit(1)

            # This is manually setting all the attributes, to be able to
            # handle optional fields and construct ConfigEntry objects
            for field in dataclasses.fields(self):
                if field.name not in config.keys():
                    if field.default is not dataclasses.MISSING:
                        continue
                    self.logger.error(
                        f'Expected option \"{field.name}\"')
                    sys.exit(1)

                elif field.name == 'analyze':
                    self.analyze = [AnalyzeConfigEntry(**c).compile_pattern()
                                    for c in config.pop('analyze')]
                else:
                    self.logger.debug(f'{field.name}: {config[field.name]}')
                    setattr(self, field.name, config[field.name])
