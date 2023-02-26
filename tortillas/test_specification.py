'''This module handles the test specification headers of tortillas tests.'''

from __future__ import annotations

import sys
import pathlib
import dataclasses
import yaml

from .utils import get_logger
from .constants import TEST_FOLDER_PATH


def get_test_specs(sweb_src_folder: str, test_glob: str) -> list[TestSpec]:
    '''
    Gets all TestSpecs (yaml test headers) that can be found at
    `sweb_src_folder/TEST_FOLDER_PATH/{test_glob}.c`
    '''
    file_paths = list(pathlib.Path(
        f'{sweb_src_folder}/{TEST_FOLDER_PATH}').glob(f'{test_glob}.c'))

    specs = []
    for file_path in file_paths:
        try:
            specs.append(TestSpec(file_path.stem, file_path))
        except NoTestSpecFound:
            continue

    specs.sort(key=(lambda spec: spec.test_name), reverse=True)
    return specs


def filter_test_specs(specs: list[TestSpec], categories: list[str],
                      tags: list[str]) -> list[TestSpec]:
    '''
    Filter for `specs`, where spec.category is in `categories` and
    for specs where any tag in spec.tags matches with `tags`.
    '''
    if categories:
        specs = [spec for spec in specs
                 if spec.category in categories]

    if tags:
        specs = [spec for spec in specs
                 if any(tag in spec.tags for tag in tags)]
    return specs


class NoTestSpecFound(Exception):
    '''Will be raised, if a test file does not contain test spec header.'''


@dataclasses.dataclass(init=False)
class TestSpec():
    '''
    Test specification class.

    A valid test specification header requires the following format:

        - First line must start a block comment '/*'
        - First or second line must contain '---' to denote a yaml section
        - The content of the block command needs to be valid yaml
        - `category` and `description` are required

    The constructor of this class will automatically open `test_src_path` and
    parse the yaml header.

    To add a new test specification field, you ONLY have to add a member
    in this class. If one specifies a default value, the field is optional,
    otherwise it is required.
    '''

    category: str
    description: str

    disabled: bool = False
    timeout: int = 0

    expect_timeout: bool = False
    expect_exit_codes: list[int] | None = None

    tags: list[str] | None = None

    def __init__(self, test_name: str, test_src_path: str):
        ''':raises: NoTestSpecFound: `yaml.safe_loads` failed'''
        self.test_name = test_name
        self.test_src_path = test_src_path
        self.logger = get_logger(f'Test config for {test_name}', prefix=True)

        try:
            config = self._parse_yaml_config_header(test_src_path)
        except yaml.YAMLError as exc:
            self.logger.error(exc)
            raise NoTestSpecFound from exc

        for field in dataclasses.fields(self):
            if field.name not in config.keys():
                if field.default is not dataclasses.MISSING:
                    continue
                self.logger.error(f'Expected option \"{field.name}\"')
                sys.exit(1)

            if field.name == 'tags':
                self.tags = [str(tag) for tag in config.pop('tags')]
            else:
                setattr(self, field.name, config[field.name])

    @staticmethod
    def _parse_yaml_config_header(test_src_path: str) -> dict:
        ''':raises: NoTestSpecFound: no valid yaml header was found'''
        test_config_raw = ''
        with open(test_src_path, 'r') as test_src_file:
            lines = test_src_file.readlines()
            if (not lines[0].startswith('/*') or
                    ('---' not in lines[0] and
                     '---' not in lines[1])):
                raise NoTestSpecFound

            for line in lines[1:]:
                if '*/' in line:
                    break
                test_config_raw += line

            return yaml.safe_load(test_config_raw)
