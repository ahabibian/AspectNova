from pathlib import Path

from agent.config import load_config


def test_load_config_applies_defaults():
    cfg_path = Path("config.v1.yaml")
    cfg = load_config(cfg_path)

    # defaults باید ست شده باشند
    assert "output" in cfg
    assert "dir" in cfg["output"]
    assert cfg["output"]["dir"] == "output"

    assert "scan" in cfg
    assert isinstance(cfg["scan"].get("roots"), list)
