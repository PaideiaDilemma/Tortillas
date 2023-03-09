from pathlib import Path
from tortillas.tortillas_config import TortillasConfig


def test_parse_base_config():
    config = TortillasConfig(Path("./tortillas_config.yml"))

    assert config
