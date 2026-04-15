"""
数据库查询引擎

提供安全的参数化 SQL 查询、表结构信息获取等功能。
所有查询均为只读，通过 PRAGMA query_only 保护。
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Optional

from .safety import is_readonly_sql

# Sensitive columns that must NOT appear in external output.
# Internal methods (e.g. get_manager_name) can still access them.
SENSITIVE_COLUMNS = frozenset({"manager_id"})


def strip_sensitive_fields(result: dict[str, Any]) -> dict[str, Any]:
    """Remove sensitive columns from query result rows."""
    if not result.get("rows"):
        return result
    filtered_rows = [
        {k: v for k, v in row.items() if k not in SENSITIVE_COLUMNS}
        for row in result["rows"]
    ]
    filtered_cols = [
        c for c in result.get("columns", []) if c not in SENSITIVE_COLUMNS
    ]
    return {**result, "rows": filtered_rows, "columns": filtered_cols}


class DBEngine:
    """SQLite database query engine with read-only enforcement."""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._validate_path()

    def _validate_path(self) -> None:
        if not Path(self._db_path).exists():
            raise FileNotFoundError(f"数据库文件不存在: {self._db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only = ON")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def get_schema_info(self) -> str:
        """Return all table schemas and sample data as formatted text."""
        conn = self._get_connection()
        try:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()

            parts: list[str] = []
            for (table_name,) in [tuple(r) for r in tables]:
                # Table DDL
                ddl = conn.execute(
                    "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                    (table_name,),
                ).fetchone()
                parts.append(f"-- 表: {table_name}")
                if ddl:
                    parts.append(ddl[0])

                # Column info
                cols = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
                col_names = [c["name"] for c in cols]
                parts.append(f"-- 字段: {', '.join(col_names)}")

                # Row count
                count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
                parts.append(f"-- 记录数: {count}")

                # Sample rows (3)
                rows = conn.execute(f"SELECT * FROM {table_name} LIMIT 3").fetchall()
                if rows:
                    parts.append("-- 示例数据:")
                    for row in rows:
                        parts.append(f"--   {dict(row)}")

                parts.append("")

            return "\n".join(parts)
        finally:
            conn.close()

    def execute_query(self, sql: str, params: Optional[tuple] = None) -> dict[str, Any]:
        """
        Execute a read-only parameterized SQL query.

        Args:
            sql: SQL SELECT statement with ? placeholders.
            params: Tuple of parameter values.

        Returns:
            Dict with 'columns', 'rows', 'row_count', and 'sql' keys.
        """
        # Safety check
        ok, msg = is_readonly_sql(sql)
        if not ok:
            return {"error": msg, "rows": [], "row_count": 0}

        conn = self._get_connection()
        try:
            cursor = conn.execute(sql, params or ())
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = [dict(row) for row in cursor.fetchall()]
            return {
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
                "sql": sql,
            }
        except sqlite3.Error as e:
            return {"error": f"SQL 执行错误: {e}", "rows": [], "row_count": 0}
        finally:
            conn.close()

    # ---- Convenience query methods (pre-built safe queries) ----

    def query_employee(
        self,
        name: Optional[str] = None,
        employee_id: Optional[str] = None,
        department: Optional[str] = None,
    ) -> dict[str, Any]:
        """Query employees with optional filters. Resolves manager_id to manager_name."""
        conditions: list[str] = ["e.status = 'active'"]
        params: list[str] = []

        if name:
            conditions.append("e.name = ?")
            params.append(name)
        if employee_id:
            conditions.append("e.employee_id = ?")
            params.append(employee_id)
        if department:
            conditions.append("e.department = ?")
            params.append(department)

        where = " AND ".join(conditions)
        sql = (
            "SELECT e.employee_id, e.name, e.department, e.level, "
            "e.hire_date, m.name AS manager_name, e.email, e.status "
            "FROM employees e "
            "LEFT JOIN employees m ON e.manager_id = m.employee_id "
            f"WHERE {where}"
        )
        return self.execute_query(sql, tuple(params))

    def query_employee_projects(self, employee_id: str) -> dict[str, Any]:
        """Query all projects an employee participates in."""
        sql = """
            SELECT p.project_id, p.name AS project_name, p.status AS project_status,
                   pm.role, pm.join_date
            FROM project_members pm
            JOIN projects p ON pm.project_id = p.project_id
            WHERE pm.employee_id = ?
            ORDER BY pm.join_date
        """
        return self.execute_query(sql, (employee_id,))

    def query_attendance(
        self,
        employee_id: str,
        year: int,
        month: int,
        status_filter: Optional[str] = None,
    ) -> dict[str, Any]:
        """Query attendance records for a specific employee/month."""
        month_prefix = f"{year:04d}-{month:02d}-%"
        if status_filter:
            sql = """
                SELECT * FROM attendance
                WHERE employee_id = ? AND date LIKE ? AND status = ?
                ORDER BY date
            """
            return self.execute_query(sql, (employee_id, month_prefix, status_filter))
        else:
            sql = """
                SELECT * FROM attendance
                WHERE employee_id = ? AND date LIKE ?
                ORDER BY date
            """
            return self.execute_query(sql, (employee_id, month_prefix))

    def query_performance(
        self, employee_id: str, year: Optional[int] = None
    ) -> dict[str, Any]:
        """Query performance reviews for an employee."""
        if year:
            sql = """
                SELECT * FROM performance_reviews
                WHERE employee_id = ? AND year = ?
                ORDER BY quarter
            """
            return self.execute_query(sql, (employee_id, year))
        else:
            sql = """
                SELECT * FROM performance_reviews
                WHERE employee_id = ?
                ORDER BY year, quarter
            """
            return self.execute_query(sql, (employee_id,))

    def query_department_members(self, department: str) -> dict[str, Any]:
        """Query all active members of a department."""
        sql = """
            SELECT employee_id, name, level, hire_date, email
            FROM employees
            WHERE department = ? AND status = 'active'
            ORDER BY employee_id
        """
        return self.execute_query(sql, (department,))

    def query_projects_by_status(self, status: str) -> dict[str, Any]:
        """Query projects by status."""
        sql = """
            SELECT p.*, e.name AS lead_name
            FROM projects p
            LEFT JOIN employees e ON p.lead_id = e.employee_id
            WHERE p.status = ?
            ORDER BY p.start_date
        """
        return self.execute_query(sql, (status,))

    def find_employee_by_name(self, name: str) -> dict[str, Any]:
        """Find employee by name (fuzzy match). Resolves manager_id to manager_name."""
        sql = """
            SELECT e.employee_id, e.name, e.department, e.level,
                   e.hire_date, m.name AS manager_name, e.email, e.status
            FROM employees e
            LEFT JOIN employees m ON e.manager_id = m.employee_id
            WHERE e.name LIKE ?
        """
        return self.execute_query(sql, (f"%{name}%",))

    def get_manager_name(self, manager_id: str) -> Optional[str]:
        """Resolve manager_id to manager name."""
        result = self.execute_query(
            "SELECT name FROM employees WHERE employee_id = ?",
            (manager_id,),
        )
        if result["rows"]:
            return result["rows"][0]["name"]
        return None


def format_query_result(result: dict[str, Any]) -> str:
    """Format a query result dict as a readable JSON string."""
    return json.dumps(result, ensure_ascii=False, indent=2, default=str)
