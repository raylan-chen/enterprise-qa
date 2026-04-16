"""Tests for source registry abstractions."""

from pathlib import Path

from src.config import load_config
from src.db_engine import DBEngine
from src.interfaces import SourceRegistry
from src.kb_engine import KBEngine


BASE_DIR = str(Path(__file__).resolve().parent.parent)


def test_registry_caches_structured_source():
    cfg = load_config(base_dir=BASE_DIR)
    registry = SourceRegistry(cfg)

    first = registry.get_db_source()
    second = registry.get_db_source()

    assert isinstance(first, DBEngine)
    assert first is second


def test_registry_caches_knowledge_source():
    cfg = load_config(base_dir=BASE_DIR)
    registry = SourceRegistry(cfg)

    first = registry.get_kb_source()
    second = registry.get_kb_source()

    assert isinstance(first, KBEngine)
    assert first is second


def test_registry_exposes_default_capabilities():
    cfg = load_config(base_dir=BASE_DIR)
    registry = SourceRegistry(cfg)

    capabilities = registry.get_capability_registry().list_capabilities()

    assert "employee.lookup" in capabilities
    assert "attendance.lookup" in capabilities
    assert "projects.all" in capabilities


def test_registry_exposes_loaded_config():
    cfg = load_config(base_dir=BASE_DIR)
    registry = SourceRegistry(cfg)

    assert registry.config is cfg


def test_registry_injects_shared_capability_registry_into_db_source():
    cfg = load_config(base_dir=BASE_DIR)
    registry = SourceRegistry(cfg)

    db = registry.get_db_source()
    capabilities = registry.get_capability_registry()

    assert isinstance(db, DBEngine)
    assert db._capabilities is capabilities