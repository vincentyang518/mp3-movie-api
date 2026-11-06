from pathlib import Path
import pytest
from fastapi.testclient import TestClient
import main
from src import MovieStorage

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'storage', MovieStorage(tmp_path / 'movies.db'))
    with TestClient(main.app) as client:
        yield client

@pytest.fixture
def sample():
    return (Path(__file__).resolve().parents[1] / 'fixtures/sample_movies.csv').read_bytes()
