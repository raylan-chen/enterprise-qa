"""Tests for capability registration and execution."""

from pathlib import Path
from types import SimpleNamespace

from src.capabilities import CapabilityRegistry
from src.capabilities import QueryCapability
from src.db_engine import DBEngine
from src.query_definitions import DEFAULT_CAPABILITIES, create_default_capability_registry


DB_PATH = str(Path(__file__).resolve().parent.parent / "data" / "enterprise.db")


def test_default_capability_registry_contains_expected_queries():
    registry = create_default_capability_registry()

    assert registry.list_capabilities() == sorted(c.name for c in DEFAULT_CAPABILITIES)


def test_execute_employee_lookup_capability():
    registry = create_default_capability_registry()
    db = DBEngine(DB_PATH)

    result = registry.execute("employee.lookup", db, {"name": "张三"})

    assert result["row_count"] == 1
    assert result["rows"][0]["department"] == "研发部"
    assert result["rows"][0]["manager_name"] == "CEO"


def test_execute_projects_all_capability():
    registry = create_default_capability_registry()
    db = DBEngine(DB_PATH)

    result = registry.execute("projects.all", db, {})

    assert result["row_count"] == 5


def test_execute_attendance_capability_with_status_filter():
    registry = create_default_capability_registry()
    db = DBEngine(DB_PATH)

    result = registry.execute(
        "attendance.lookup",
        db,
        {
            "employee_id": "EMP-001",
            "year": 2026,
            "month": 2,
            "status_filter": "late",
        },
    )

    assert result["row_count"] == 2


def test_capability_registry_raises_on_unknown_capability():
    registry = CapabilityRegistry()
    db = DBEngine(DB_PATH)

    try:
        registry.execute("missing", db, {})
        raised = False
    except KeyError:
        raised = True

    assert raised is True


def test_capability_registry_rejects_non_readonly_sql():
    registry = CapabilityRegistry()
    registry.register(
        QueryCapability(
            name="unsafe",
            description="unsafe query",
            sql_builder=lambda params: ("DELETE FROM employees", tuple()),
        )
    )

    result = registry.execute("unsafe", SimpleNamespace(), {})

    assert "error" in result
    assert result["row_count"] == 0


def test_capability_registry_applies_post_process():
    registry = CapabilityRegistry()
    registry.register(
        QueryCapability(
            name="processed",
            description="processed query",
            sql_builder=lambda params: ("SELECT 1 AS val", tuple()),
            post_process=lambda result: {**result, "processed": True},
        )
    )

    source = SimpleNamespace(
        execute_query=lambda sql, sql_params: {
            "columns": ["val"],
            "rows": [{"val": 1}],
            "row_count": 1,
            "sql": sql,
        }
    )

    result = registry.execute("processed", source, {})

    assert result["processed"] is True
    assert result["rows"][0]["val"] == 1