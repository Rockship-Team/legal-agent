"""Pytest configuration and fixtures"""

import pytest
import os
import tempfile


@pytest.fixture(autouse=True)
def test_env(tmp_path, monkeypatch):
    """Set up test environment with temporary database"""
    db_path = tmp_path / "test.db"
    chroma_path = tmp_path / "chroma"

    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("CHROMA_PATH", str(chroma_path))
    monkeypatch.setenv("GROQ_API_KEY", "test_key")

    yield

    # Cleanup handled by tmp_path fixture
