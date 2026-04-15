"""Tests for db_engine module."""

import sqlite3
import pytest
from pathlib import Path

from src.db_engine import DBEngine, format_query_result, strip_sensitive_fields, SENSITIVE_COLUMNS

# Path to the test database
DB_PATH = str(
    Path(__file__).resolve().parent.parent
    / "data"
    / "enterprise.db"
)


@pytest.fixture
def db():
    return DBEngine(DB_PATH)


class TestDBEngine:
    """Test database engine core functionality."""

    def test_init_valid_db(self, db):
        assert db is not None

    def test_init_invalid_path(self):
        with pytest.raises(FileNotFoundError):
            DBEngine("/nonexistent/path.db")

    def test_get_schema_info(self, db):
        schema = db.get_schema_info()
        assert "employees" in schema
        assert "projects" in schema
        assert "attendance" in schema
        assert "performance_reviews" in schema

    def test_execute_query_basic(self, db):
        result = db.execute_query(
            "SELECT name FROM employees WHERE employee_id = ?", ("EMP-001",)
        )
        assert result["row_count"] == 1
        assert result["rows"][0]["name"] == "张三"

    def test_execute_query_no_results(self, db):
        result = db.execute_query(
            "SELECT * FROM employees WHERE employee_id = ?", ("EMP-999",)
        )
        assert result["row_count"] == 0
        assert result["rows"] == []

    def test_execute_query_rejects_write(self, db):
        result = db.execute_query("INSERT INTO employees VALUES ('x','y','z','a','b','c','d','e')")
        assert "error" in result

    def test_execute_query_rejects_drop(self, db):
        result = db.execute_query("DROP TABLE employees")
        assert "error" in result


class TestEmployeeQueries:
    """Test employee-specific query methods."""

    def test_query_employee_by_name(self, db):
        result = db.query_employee(name="张三")
        assert result["row_count"] == 1
        assert result["rows"][0]["department"] == "研发部"

    def test_query_employee_resolves_manager_name(self, db):
        """query_employee should return manager_name, not manager_id."""
        result = db.query_employee(name="李四")
        row = result["rows"][0]
        assert "manager_name" in row
        assert row["manager_name"] == "CEO"
        assert "manager_id" not in row

    def test_query_employee_by_id(self, db):
        result = db.query_employee(employee_id="EMP-002")
        assert result["row_count"] == 1
        assert result["rows"][0]["name"] == "李四"

    def test_query_employee_by_department(self, db):
        result = db.query_employee(department="研发部")
        # 研发部 active: 张三, 李四, 钱七, 周九 = 4
        assert result["row_count"] == 4

    def test_query_employee_not_found(self, db):
        result = db.query_employee(name="不存在的人")
        assert result["row_count"] == 0

    def test_query_excludes_resigned(self, db):
        """Default query should exclude resigned employees."""
        result = db.query_employee(name="离职员工")
        assert result["row_count"] == 0

    def test_find_employee_by_name_fuzzy(self, db):
        result = db.find_employee_by_name("张")
        assert result["row_count"] >= 1
        assert any(r["name"] == "张三" for r in result["rows"])

    def test_find_employee_resolves_manager_name(self, db):
        result = db.find_employee_by_name("张三")
        row = result["rows"][0]
        assert "manager_name" in row
        assert "manager_id" not in row


class TestProjectQueries:
    def test_query_employee_projects(self, db):
        # 张三参与 4 个项目
        result = db.query_employee_projects("EMP-001")
        assert result["row_count"] == 4
        names = {r["project_name"] for r in result["rows"]}
        assert "ReMe 记忆框架" in names

    def test_query_projects_by_status(self, db):
        result = db.query_projects_by_status("active")
        assert result["row_count"] == 2


class TestAttendanceQueries:
    def test_query_attendance_zhang_feb(self, db):
        """T08: 张三 2 月迟到 2 次."""
        result = db.query_attendance("EMP-001", 2026, 2, status_filter="late")
        assert result["row_count"] == 2

    def test_query_attendance_full_month(self, db):
        result = db.query_attendance("EMP-001", 2026, 2)
        assert result["row_count"] == 20


class TestPerformanceQueries:
    def test_query_performance_zhang_2025(self, db):
        result = db.query_performance("EMP-001", year=2025)
        assert result["row_count"] == 4
        scores = [r["kpi_score"] for r in result["rows"]]
        avg = sum(scores) / len(scores)
        assert abs(avg - 89.25) < 0.01

    def test_query_performance_wang_2025(self, db):
        """王五 2025 平均 KPI = 80."""
        result = db.query_performance("EMP-003", year=2025)
        assert result["row_count"] == 2
        scores = [r["kpi_score"] for r in result["rows"]]
        assert abs(sum(scores) / len(scores) - 80.0) < 0.01


class TestDepartmentQueries:
    def test_department_members_rd(self, db):
        """T06: 研发部 4 人."""
        result = db.query_department_members("研发部")
        assert result["row_count"] == 4

    def test_department_members_product(self, db):
        result = db.query_department_members("产品部")
        assert result["row_count"] == 3


class TestManagerResolve:
    def test_get_manager_name(self, db):
        name = db.get_manager_name("EMP-000")
        assert name == "CEO"

    def test_get_manager_name_not_found(self, db):
        name = db.get_manager_name("EMP-999")
        assert name is None


class TestFormatResult:
    def test_format_query_result(self, db):
        result = db.execute_query("SELECT 1 AS val")
        formatted = format_query_result(result)
        assert "val" in formatted


class TestStripSensitiveFields:
    def test_strips_manager_id(self):
        result = {
            "columns": ["name", "manager_id", "department"],
            "rows": [{"name": "张三", "manager_id": "EMP-000", "department": "研发部"}],
            "row_count": 1,
        }
        filtered = strip_sensitive_fields(result)
        assert "manager_id" not in filtered["columns"]
        assert "manager_id" not in filtered["rows"][0]
        assert filtered["rows"][0]["name"] == "张三"

    def test_no_rows_passthrough(self):
        result = {"columns": [], "rows": [], "row_count": 0}
        assert strip_sensitive_fields(result) == result

    def test_no_sensitive_columns_unchanged(self):
        result = {
            "columns": ["name", "department"],
            "rows": [{"name": "张三", "department": "研发部"}],
            "row_count": 1,
        }
        filtered = strip_sensitive_fields(result)
        assert filtered["rows"] == result["rows"]

    def test_raw_sql_with_manager_id_filtered(self, db):
        """Even raw SELECT * FROM employees is filtered by strip_sensitive_fields."""
        result = db.execute_query("SELECT * FROM employees WHERE employee_id = 'EMP-001'")
        filtered = strip_sensitive_fields(result)
        assert "manager_id" not in filtered["rows"][0]
        assert "manager_id" not in filtered["columns"]
