from __future__ import annotations
from typing import Optional

import sys
import yaml
import dataclasses

from utils import get_logger


class NoTestConfigFound(Exception):
    pass


@dataclasses.dataclass
class TestConfig():
    category: str
    description: str

    disabled: Optional[bool] = None

    timeout: Optional[int] = 0
    expect_timeout: Optional[bool] = None

    expect_exit_codes: Optional[list[int]] = None

    tags: Optional[list[str]] = None

    def __init__(self, test_name: str, test_src_path: str):
        self.test_name = test_name
        self.logger = get_logger(f'Test config for {test_name}', prefix=True)

        config = self.get_yaml_config_header(test_src_path)

        for field in dataclasses.fields(self):
            if field.name not in config.keys():
                if field.default is not dataclasses.MISSING:
                    continue
                self.logger.error(
                        f'Expected option \"{field.name}\"')
                sys.exit(-1)

            if field.name == 'tags':
                self.tags = [str(tag) for tag in config.pop('tags')]
            else:
                setattr(self, field.name, config[field.name])

    def get_yaml_config_header(self, test_src_path) -> dict:
        test_config_raw = ''
        out: dict = {}
        with open(test_src_path, 'r') as f:
            lines = f.readlines()
            if ('/*' not in lines[0]
                    or '#Tortillas test config' not in lines[1]):
                raise NoTestConfigFound

            for line in lines[1:]:
                if '*/' in line:
                    break
                test_config_raw += line

            try:
                out = yaml.safe_load(test_config_raw)
            except yaml.YAMLError as exc:
                self.logger.error(exc)

            return out
