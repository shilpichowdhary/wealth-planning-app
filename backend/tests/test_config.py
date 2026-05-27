import importlib
import os
import pytest


@pytest.fixture(autouse=True)
def _restore_env():
    """Snapshot/restore SECRET_KEY so tests don't bleed into each other."""
    saved = os.environ.get("SECRET_KEY")
    yield
    if saved is None:
        os.environ.pop("SECRET_KEY", None)
    else:
        os.environ["SECRET_KEY"] = saved


def _reload_config():
    from backend import config
    importlib.reload(config)
    return config


def test_secret_key_empty_default_when_env_unset(monkeypatch):
    """Assert the code-level default for secret_key is empty.

    `_env_file=None` bypasses the developer's local .env so this test is
    asserting on the field default declared in `Settings`, not whatever
    happens to be set on the contributor's machine.
    """
    monkeypatch.delenv("SECRET_KEY", raising=False)
    cfg = _reload_config()
    fresh = cfg.Settings(_env_file=None)
    assert fresh.secret_key == ""


def test_validate_secrets_raises_when_empty(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "")
    cfg = _reload_config()
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        cfg.validate_secrets(cfg.settings)


def test_validate_secrets_raises_when_too_short(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "short")
    cfg = _reload_config()
    with pytest.raises(RuntimeError, match="32"):
        cfg.validate_secrets(cfg.settings)


def test_validate_secrets_raises_on_known_default(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "dev-secret-key-change-in-production-min32")
    cfg = _reload_config()
    with pytest.raises(RuntimeError, match="default"):
        cfg.validate_secrets(cfg.settings)


def test_validate_secrets_accepts_strong_key(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "a" * 32 + "-real-random-value")
    cfg = _reload_config()
    cfg.validate_secrets(cfg.settings)  # does not raise
