"""Tests for main.py CLI handlers — direct function calls to cover main.py logic."""

import argparse
import json
import io
import sys
import pytest
from pathlib import Path
from unittest.mock import patch

# Must set up path before importing src.main
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_config
from src.main import (
    build_parser,
    cmd_schema,
    cmd_db_query,
    cmd_kb_search,
    cmd_db_employee,
    cmd_db_projects,
    cmd_db_attendance,
    cmd_db_performance,
    cmd_db_department,
    cmd_kb_list,
)

BASE_DIR = str(
    Path(__file__).resolve().parent.parent
)


@pytest.fixture
def cfg():
    return load_config(config_path=None, base_dir=BASE_DIR)


def capture_json(func, args, cfg):
    """Capture JSON output from a CLI handler."""
    buf = io.StringIO()
    with patch("sys.stdout", buf):
        func(args, cfg)
    return json.loads(buf.getvalue())


class TestCmdSchema:
    def test_schema_output(self, cfg):
        args = argparse.Namespace()
        result = capture_json(cmd_schema, args, cfg)
        assert "schema" in result
        assert "employees" in result["schema"]


class TestCmdDbQuery:
    def test_valid_select(self, cfg):
        args = argparse.Namespace(
            sql="SELECT name FROM employees WHERE employee_id = ?",
            params='["EMP-001"]',
        )
        result = capture_json(cmd_db_query, args, cfg)
        assert result["row_count"] == 1
        assert result["rows"][0]["name"] == "张三"

    def test_no_params(self, cfg):
        args = argparse.Namespace(
            sql="SELECT COUNT(*) AS cnt FROM employees",
            params=None,
        )
        result = capture_json(cmd_db_query, args, cfg)
        assert result["rows"][0]["cnt"] == 10

    def test_reject_write_sql(self, cfg):
        args = argparse.Namespace(
            sql="DROP TABLE employees",
            params=None,
        )
        with pytest.raises(SystemExit):
            capture_json(cmd_db_query, args, cfg)

    def test_reject_injection(self, cfg):
        args = argparse.Namespace(
            sql="SELECT * FROM users WHERE '1'='1'",
            params=None,
        )
        with pytest.raises(SystemExit):
            capture_json(cmd_db_query, args, cfg)


class TestCmdKbSearch:
    def test_search_normal(self, cfg):
        args = argparse.Namespace(query="年假怎么计算", top_k=3)
        result = capture_json(cmd_kb_search, args, cfg)
        assert result["total"] > 0
        assert "年假" in result["results"][0]["content"] or "年假" in result["results"][0]["section"]

    def test_search_empty_rejected(self, cfg):
        args = argparse.Namespace(query="   ", top_k=3)
        with pytest.raises(SystemExit):
            capture_json(cmd_kb_search, args, cfg)


class TestCmdDbEmployee:
    def test_by_name(self, cfg):
        args = argparse.Namespace(name="张三", employee_id=None, department=None)
        result = capture_json(cmd_db_employee, args, cfg)
        assert result["row_count"] == 1
        assert result["rows"][0]["department"] == "研发部"

    def test_by_name_no_manager_id_leak(self, cfg):
        """CLI output must NOT contain manager_id (sensitive field)."""
        args = argparse.Namespace(name="李四", employee_id=None, department=None)
        result = capture_json(cmd_db_employee, args, cfg)
        row = result["rows"][0]
        assert "manager_id" not in row
        assert row.get("manager_name") == "CEO"

    def test_by_department(self, cfg):
        args = argparse.Namespace(name=None, employee_id=None, department="研发部")
        result = capture_json(cmd_db_employee, args, cfg)
        assert result["row_count"] == 4

    def test_not_found(self, cfg):
        args = argparse.Namespace(name=None, employee_id="EMP-999", department=None)
        result = capture_json(cmd_db_employee, args, cfg)
        assert result["row_count"] == 0


class TestCmdDbProjects:
    def test_by_employee(self, cfg):
        args = argparse.Namespace(employee_id="EMP-001", status=None)
        result = capture_json(cmd_db_projects, args, cfg)
        assert result["row_count"] == 4

    def test_by_status(self, cfg):
        args = argparse.Namespace(employee_id=None, status="active")
        result = capture_json(cmd_db_projects, args, cfg)
        assert result["row_count"] == 2

    def test_all_projects(self, cfg):
        args = argparse.Namespace(employee_id=None, status=None)
        result = capture_json(cmd_db_projects, args, cfg)
        assert result["row_count"] == 5


class TestCmdDbAttendance:
    def test_late_count(self, cfg):
        args = argparse.Namespace(
            employee_id="EMP-001", year=2026, month=2, status="late"
        )
        result = capture_json(cmd_db_attendance, args, cfg)
        assert result["row_count"] == 2

    def test_full_month(self, cfg):
        args = argparse.Namespace(
            employee_id="EMP-001", year=2026, month=2, status=None
        )
        result = capture_json(cmd_db_attendance, args, cfg)
        assert result["row_count"] == 20


class TestCmdDbPerformance:
    def test_with_year(self, cfg):
        args = argparse.Namespace(employee_id="EMP-001", year=2025)
        result = capture_json(cmd_db_performance, args, cfg)
        assert result["row_count"] == 4

    def test_without_year(self, cfg):
        args = argparse.Namespace(employee_id="EMP-001", year=None)
        result = capture_json(cmd_db_performance, args, cfg)
        assert result["row_count"] == 4


class TestCmdDbDepartment:
    def test_department_members(self, cfg):
        args = argparse.Namespace(department="产品部")
        result = capture_json(cmd_db_department, args, cfg)
        assert result["row_count"] == 3


class TestCmdKbList:
    def test_list_documents(self, cfg):
        args = argparse.Namespace()
        result = capture_json(cmd_kb_list, args, cfg)
        assert result["total_sections"] > 0
        names = {d["file_name"] for d in result["documents"]}
        assert "hr_policies.md" in names


class TestBuildParser:
    def test_parser_creation(self):
        parser = build_parser()
        assert parser is not None

    def test_parse_schema(self):
        parser = build_parser()
        args = parser.parse_args(["schema"])
        assert args.command == "schema"

    def test_parse_db_query(self):
        parser = build_parser()
        args = parser.parse_args(["db-query", "--sql", "SELECT 1"])
        assert args.command == "db-query"
        assert args.sql == "SELECT 1"
