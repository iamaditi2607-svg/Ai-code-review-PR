import run
import pytest


def test_server_uses_default_host_and_port(monkeypatch):
    settings = {}
    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.setattr(run.uvicorn, "run", lambda app, **kwargs: settings.update(kwargs))

    run.main()

    assert settings == {"host": "0.0.0.0", "port": 8000}


def test_server_uses_host_and_port_from_environment(monkeypatch):
    settings = {}
    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.setenv("PORT", "9123")
    monkeypatch.setattr(run.uvicorn, "run", lambda app, **kwargs: settings.update(kwargs))

    run.main()

    assert settings == {"host": "127.0.0.1", "port": 9123}


def test_server_rejects_invalid_port(monkeypatch):
    monkeypatch.setenv("PORT", "70000")
    monkeypatch.setattr(run.uvicorn, "run", lambda app, **kwargs: None)

    with pytest.raises(ValueError, match="PORT must be between 0 and 65535"):
        run.main()
