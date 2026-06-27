from pathlib import Path

from lottery.config import load_config

CONFIG_BODY = (
    '[paths]\ndb_path="a.sqlite"\ncsv_path="a.csv"\n'
    '[analysis]\ndefault_window=50\n[logging]\nlevel="INFO"\n'
)


def test_load_config_defaults(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(CONFIG_BODY)
    cfg = load_config(cfg_file)
    assert cfg.default_window == 50
    assert cfg.db_path == Path("a.sqlite")


def test_load_config_env_override(tmp_path, monkeypatch):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(CONFIG_BODY)
    monkeypatch.setenv("LOTTERY_DEFAULT_WINDOW", "7")
    cfg = load_config(cfg_file)
    assert cfg.default_window == 7
