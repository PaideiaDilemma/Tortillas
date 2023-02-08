from tortillas.tortillas_config import TortillasConfig


def test_parse_base_config():
    config = TortillasConfig('./examples/base/tortillas_config.yml')

    assert config


def test_parse_extended_config():
    config = TortillasConfig('./examples/extended/tortillas_config.yml')

    assert config
