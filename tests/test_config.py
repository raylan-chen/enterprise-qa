"""Tests for config module."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from src.config import Config, DatabaseConfig, KnowledgeBaseConfig, load_config


class TestConfig:
    """Test configuration loading and priority."""

    def test_default_config(self, tmp_path):
        """Defaults should be applied when no config file or env vars."""
        cfg = load_config(config_path=None, base_dir=tmp_path)
        assert cfg.database.type == "sqlite"
        assert cfg.timezone == "Asia/Shanghai"

    def test_yaml_config(self, tmp_path):
        """YAML file values should override defaults."""
        cfg_data = {
            "database": {"type": "sqlite", "path": "./test.db"},
            "knowledge_base": {"root_path": "./kb"},
            "timezone": "UTC",
        }
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.dump(cfg_data), encoding="utf-8")

        cfg = load_config(config_path=str(cfg_file), base_dir=tmp_path)
        assert cfg.database.path == "./test.db"
        assert cfg.knowledge_base.root_path == "./kb"
        assert cfg.timezone == "UTC"
        assert cfg.db_path == str(tmp_path / "test.db")

    def test_env_vars_override_yaml(self, tmp_path, monkeypatch):
        """Environment variables should override YAML values."""
        cfg_data = {"database": {"path": "./yaml.db"}}
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.dump(cfg_data), encoding="utf-8")

        monkeypatch.setenv("ENTERPRISE_QA_DB_PATH", "./env.db")
        cfg = load_config(config_path=str(cfg_file), base_dir=tmp_path)
        assert cfg.database.path == "./env.db"
        assert cfg.db_path == str(tmp_path / "env.db")

    def test_env_vars_without_yaml(self, tmp_path, monkeypatch):
        """Env vars should work without any YAML file."""
        db_path = str(tmp_path / "test.db")
        kb_path = str(tmp_path / "knowledge")
        monkeypatch.setenv("ENTERPRISE_QA_DB_PATH", db_path)
        monkeypatch.setenv("ENTERPRISE_QA_KB_PATH", kb_path)
        cfg = load_config(config_path=None, base_dir=tmp_path)
        assert cfg.db_path == db_path
        assert cfg.kb_path == kb_path

    def test_resolve_relative_paths(self, tmp_path):
        """Relative paths should resolve against base_dir."""
        cfg = Config()
        cfg.database.path = "./data/test.db"
        cfg.knowledge_base.root_path = "./docs"
        cfg.resolve_paths(tmp_path)
        assert cfg.db_path == str(tmp_path / "data" / "test.db")
        assert cfg.kb_path == str(tmp_path / "docs")

    def test_resolve_paths_tolerates_duplicated_base_segment(self, tmp_path):
        """Passing base_dir=data should still resolve ./data/... correctly."""
        data_dir = tmp_path / "data"
        knowledge_dir = data_dir / "knowledge"
        data_dir.mkdir()
        knowledge_dir.mkdir()
        (data_dir / "enterprise.db").write_text("", encoding="utf-8")

        cfg = Config()
        cfg.database.path = "./data/enterprise.db"
        cfg.knowledge_base.root_path = "./data/knowledge"

        cfg.resolve_paths(data_dir)

        assert cfg.db_path == str(data_dir / "enterprise.db")
        assert cfg.kb_path == str(knowledge_dir)

    def test_load_config_with_data_base_dir(self, tmp_path):
        """CLI-style base_dir=./data should not produce data/data paths."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "enterprise.db").write_text("", encoding="utf-8")
        (data_dir / "knowledge").mkdir()

        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(
            yaml.dump(
                {
                    "database": {"path": "./data/enterprise.db"},
                    "knowledge_base": {"root_path": "./data/knowledge"},
                }
            ),
            encoding="utf-8",
        )

        cfg = load_config(config_path=str(cfg_file), base_dir=data_dir)

        assert cfg.db_path == str(data_dir / "enterprise.db")
        assert cfg.kb_path == str(data_dir / "knowledge")

    def test_load_config_with_data_base_dir_before_targets_exist(self, tmp_path):
        """Path deduplication should not depend on files already existing."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(
            yaml.dump(
                {
                    "database": {"path": "./data/enterprise.db"},
                    "knowledge_base": {"root_path": "./data/knowledge"},
                }
            ),
            encoding="utf-8",
        )

        cfg = load_config(config_path=str(cfg_file), base_dir=data_dir)

        assert cfg.db_path == str(data_dir / "enterprise.db")
        assert cfg.kb_path == str(data_dir / "knowledge")

    def test_missing_yaml_file(self, tmp_path):
        """Non-existent YAML path should not crash — use defaults."""
        cfg = load_config(
            config_path=str(tmp_path / "nonexistent.yaml"),
            base_dir=tmp_path,
        )
        assert cfg.database.type == "sqlite"
