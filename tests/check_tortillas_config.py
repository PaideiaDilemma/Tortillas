from tortillas.tortillas_config import TortillasConfig


def test_parse_base_config():
    config = TortillasConfig("./tortillas_config.yml")

    assert config
