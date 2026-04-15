"""
配置管理模块

支持环境变量 > config.yaml > 默认值 的优先级链。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class DatabaseConfig:
    type: str = "sqlite"
    path: str = "./data/enterprise.db"


@dataclass
class KnowledgeBaseConfig:
    root_path: str = "./data/knowledge"
    index_type: str = "bm25"


@dataclass
class LoggingConfig:
    level: str = "INFO"
    file: Optional[str] = None


@dataclass
class Config:
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    knowledge_base: KnowledgeBaseConfig = field(default_factory=KnowledgeBaseConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    timezone: str = "Asia/Shanghai"

    # Resolved absolute paths (set after loading)
    db_path: str = ""
    kb_path: str = ""

    def resolve_paths(self, base_dir: str | Path) -> None:
        """Resolve relative paths against a base directory."""
        base = Path(base_dir).resolve()
        db_raw = Path(self.database.path)
        kb_raw = Path(self.knowledge_base.root_path)
        self.db_path = str(db_raw if db_raw.is_absolute() else base / db_raw)
        self.kb_path = str(kb_raw if kb_raw.is_absolute() else base / kb_raw)


def _load_yaml(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_config(
    config_path: Optional[str | Path] = None,
    base_dir: Optional[str | Path] = None,
) -> Config:
    """
    Load configuration with priority: env vars > yaml > defaults.

    Args:
        config_path: Optional path to config.yaml.
        base_dir: Base directory for resolving relative paths.
                  Defaults to parent of config_path or cwd.
    """
    cfg = Config()

    # --- Layer 1: YAML file ---
    if config_path is None:
        # Try common locations
        for candidate in ["config.yaml", "config.yml"]:
            if Path(candidate).exists():
                config_path = candidate
                break

    if config_path is not None:
        data = _load_yaml(config_path)
        if "database" in data:
            db = data["database"]
            cfg.database.type = db.get("type", cfg.database.type)
            cfg.database.path = db.get("path", cfg.database.path)
        if "knowledge_base" in data:
            kb = data["knowledge_base"]
            cfg.knowledge_base.root_path = kb.get("root_path", cfg.knowledge_base.root_path)
            cfg.knowledge_base.index_type = kb.get("index_type", cfg.knowledge_base.index_type)
        if "logging" in data:
            log = data["logging"]
            cfg.logging.level = log.get("level", cfg.logging.level)
            cfg.logging.file = log.get("file", cfg.logging.file)
        cfg.timezone = data.get("timezone", cfg.timezone)

    # --- Layer 2: Environment variables (highest priority) ---
    env_db = os.environ.get("ENTERPRISE_QA_DB_PATH")
    if env_db:
        cfg.database.path = env_db

    env_kb = os.environ.get("ENTERPRISE_QA_KB_PATH")
    if env_kb:
        cfg.knowledge_base.root_path = env_kb

    # --- Resolve paths ---
    if base_dir is None:
        if config_path is not None:
            base_dir = Path(config_path).resolve().parent
        else:
            base_dir = Path.cwd()

    cfg.resolve_paths(base_dir)
    return cfg
