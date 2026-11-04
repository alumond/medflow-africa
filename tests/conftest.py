"""Isolated repositories and reproducible fixtures; no test calls external AI."""

import pytest
from fastapi.testclient import TestClient

from app.data.store import Store
from app.services.service import Service


@pytest.fixture(scope="session")
def dataset(tmp_path_factory):
    store = Store(str(tmp_path_factory.mktemp("source") / "demo.sqlite"))
    svc = Service(store)
    svc.load_demo()
    return store.latest()


@pytest.fixture
def svc(tmp_path, dataset):
    store = Store(str(tmp_path / "test.sqlite"))
    store.save_import({k: v for k, v in dataset.items() if k not in ("import_id", "created_at")})
    return Service(store)


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("MEDFLOW_DB", str(tmp_path / "api.sqlite"))
    from app.main import app

    with TestClient(app) as value:
        yield value
