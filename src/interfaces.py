"""Source abstractions and registry for concrete engine implementations."""

from __future__ import annotations

from typing import Any, Optional, Protocol

from .capabilities import CapabilityRegistry
from .config import Config
from .query_definitions import create_default_capability_registry


class StructuredSource(Protocol):
    """Protocol for structured, read-only data sources."""

    def get_schema_info(self) -> str:
        """Return schema information as formatted text."""

    def execute_query(
        self, sql: str, params: Optional[tuple] = None
    ) -> dict[str, Any]:
        """Execute a read-only query and return a structured result."""


class KnowledgeSource(Protocol):
    """Protocol for searchable knowledge sources."""

    def search(self, query: str, top_k: int = 3) -> list[Any]:
        """Search the source and return ranked results."""

    def get_document_list(self) -> list[dict[str, Any]]:
        """Return indexed document metadata."""

    @property
    def section_count(self) -> int:
        """Return indexed section count."""


class SourceRegistry:
    """Lazy registry for the configured structured and knowledge sources."""

    def __init__(self, cfg: Config):
        self._cfg = cfg
        self._db_source: Optional[StructuredSource] = None
        self._kb_source: Optional[KnowledgeSource] = None
        self._capability_registry: Optional[CapabilityRegistry] = None

    @property
    def config(self) -> Config:
        return self._cfg

    def get_db_source(self) -> StructuredSource:
        if self._db_source is None:
            from .db_engine import DBEngine

            self._db_source = DBEngine(
                self._cfg.db_path,
                capabilities=self.get_capability_registry(),
            )
        return self._db_source

    def get_kb_source(self) -> KnowledgeSource:
        if self._kb_source is None:
            from .kb_engine import KBEngine

            self._kb_source = KBEngine(self._cfg.kb_path)
        return self._kb_source

    def get_capability_registry(self) -> CapabilityRegistry:
        if self._capability_registry is None:
            self._capability_registry = create_default_capability_registry()
        return self._capability_registry