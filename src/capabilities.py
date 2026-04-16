"""Declarative registry for structured query capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional

from .safety import is_readonly_sql


SqlBuilder = Callable[[Mapping[str, Any]], tuple[str, tuple[Any, ...]]]
PostProcessor = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class QueryCapability:
    """Named structured query capability."""

    name: str
    description: str
    sql_builder: SqlBuilder
    post_process: Optional[PostProcessor] = None


class CapabilityRegistry:
    """Registry for executing named query capabilities."""

    def __init__(self) -> None:
        self._capabilities: dict[str, QueryCapability] = {}

    def register(self, capability: QueryCapability) -> None:
        self._capabilities[capability.name] = capability

    def get(self, name: str) -> QueryCapability:
        if name not in self._capabilities:
            raise KeyError(f"未知查询能力: {name}")
        return self._capabilities[name]

    def list_capabilities(self) -> list[str]:
        return sorted(self._capabilities)

    def execute(
        self,
        name: str,
        source,
        params: Mapping[str, Any],
    ) -> dict[str, Any]:
        capability = self.get(name)
        sql, sql_params = capability.sql_builder(params)

        ok, msg = is_readonly_sql(sql)
        if not ok:
            return {"error": msg, "rows": [], "row_count": 0}

        result = source.execute_query(sql, sql_params)
        if capability.post_process:
            return capability.post_process(result)
        return result