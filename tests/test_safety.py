"""Tests for safety module."""

import pytest

from src.safety import (
    detect_sql_injection,
    is_readonly_sql,
    validate_input,
    sanitize_for_display,
    MAX_INPUT_LENGTH,
)


class TestSQLInjectionDetection:
    """Test SQL injection pattern detection."""

    @pytest.mark.parametrize(
        "text",
        [
            "张三的部门是什么",
            "SELECT name FROM employees",
            "年假怎么计算",
            "王五符合晋升条件吗",
            "EMP-001",
        ],
    )
    def test_safe_inputs(self, text):
        safe, msg = detect_sql_injection(text)
        assert safe is True

    @pytest.mark.parametrize(
        "text",
        [
            "' OR '1'='1",
            "1; DROP TABLE employees",
            "UNION SELECT * FROM sqlite_master",
            "'; DELETE FROM employees--",
            "admin'--",
            "INSERT INTO employees VALUES('x','y')",
            "UPDATE employees SET name='hacked'",
        ],
    )
    def test_injection_detected(self, text):
        safe, msg = detect_sql_injection(text)
        assert safe is False
        assert "SQL 注入" in msg or "注入" in msg

    def test_empty_input(self):
        safe, msg = detect_sql_injection("")
        assert safe is True

    def test_exam_t11_case(self):
        """T11: SELECT * FROM users WHERE '1'='1 should be caught."""
        safe, msg = detect_sql_injection("SELECT * FROM users WHERE '1'='1")
        assert safe is False


class TestReadOnlySQL:
    """Test read-only SQL validation."""

    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT * FROM employees",
            "SELECT COUNT(*) FROM projects WHERE status = 'active'",
            "PRAGMA table_info(employees)",
            "EXPLAIN SELECT * FROM employees",
            "WITH cte AS (SELECT 1) SELECT * FROM cte",
        ],
    )
    def test_readonly_allowed(self, sql):
        ok, msg = is_readonly_sql(sql)
        assert ok is True

    @pytest.mark.parametrize(
        "sql",
        [
            "INSERT INTO employees VALUES('x','y')",
            "UPDATE employees SET name='hack'",
            "DELETE FROM employees",
            "DROP TABLE employees",
            "ALTER TABLE employees ADD COLUMN hack TEXT",
            "CREATE TABLE hack (id INT)",
        ],
    )
    def test_write_rejected(self, sql):
        ok, msg = is_readonly_sql(sql)
        assert ok is False

    def test_empty_sql(self):
        ok, msg = is_readonly_sql("")
        assert ok is False

    def test_select_with_embedded_drop(self):
        """SELECT containing DROP should be caught."""
        ok, msg = is_readonly_sql("SELECT 1; DROP TABLE employees")
        assert ok is False


class TestInputValidation:
    """Test user input validation."""

    def test_normal_input(self):
        ok, msg = validate_input("张三的部门是什么？")
        assert ok is True

    def test_empty_input(self):
        ok, msg = validate_input("")
        assert ok is False

    def test_whitespace_only(self):
        ok, msg = validate_input("   ")
        assert ok is False

    def test_too_long_input(self):
        ok, msg = validate_input("a" * (MAX_INPUT_LENGTH + 1))
        assert ok is False
        assert "超出限制" in msg

    def test_injection_in_input(self):
        ok, msg = validate_input("'; DROP TABLE users--")
        assert ok is False


class TestSanitize:
    def test_strip_control_chars(self):
        assert sanitize_for_display("hello\x00world") == "helloworld"

    def test_keep_normal_text(self):
        assert sanitize_for_display("你好世界") == "你好世界"
