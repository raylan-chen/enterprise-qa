"""Default structured query capability definitions."""

from __future__ import annotations

from typing import Any, Mapping

from .capabilities import CapabilityRegistry, QueryCapability


def _build_employee_query(params: Mapping[str, Any]) -> tuple[str, tuple[Any, ...]]:
    conditions: list[str] = ["e.status = 'active'"]
    values: list[str] = []

    name = params.get("name")
    employee_id = params.get("employee_id")
    department = params.get("department")

    if name:
        conditions.append("e.name = ?")
        values.append(name)
    if employee_id:
        conditions.append("e.employee_id = ?")
        values.append(employee_id)
    if department:
        conditions.append("e.department = ?")
        values.append(department)

    where = " AND ".join(conditions)
    sql = (
        "SELECT e.employee_id, e.name, e.department, e.level, "
        "e.hire_date, m.name AS manager_name, e.email, e.status "
        "FROM employees e "
        "LEFT JOIN employees m ON e.manager_id = m.employee_id "
        f"WHERE {where}"
    )
    return sql, tuple(values)


def _build_employee_projects_query(
    params: Mapping[str, Any]
) -> tuple[str, tuple[Any, ...]]:
    sql = """
        SELECT p.project_id, p.name AS project_name, p.status AS project_status,
               pm.role, pm.join_date
        FROM project_members pm
        JOIN projects p ON pm.project_id = p.project_id
        WHERE pm.employee_id = ?
        ORDER BY pm.join_date
    """
    return sql, (params["employee_id"],)


def _build_attendance_query(params: Mapping[str, Any]) -> tuple[str, tuple[Any, ...]]:
    month_prefix = f"{int(params['year']):04d}-{int(params['month']):02d}-%"
    status_filter = params.get("status_filter")
    if status_filter:
        sql = """
            SELECT * FROM attendance
            WHERE employee_id = ? AND date LIKE ? AND status = ?
            ORDER BY date
        """
        return sql, (params["employee_id"], month_prefix, status_filter)

    sql = """
        SELECT * FROM attendance
        WHERE employee_id = ? AND date LIKE ?
        ORDER BY date
    """
    return sql, (params["employee_id"], month_prefix)


def _build_performance_query(params: Mapping[str, Any]) -> tuple[str, tuple[Any, ...]]:
    year = params.get("year")
    if year is not None:
        sql = """
            SELECT * FROM performance_reviews
            WHERE employee_id = ? AND year = ?
            ORDER BY quarter
        """
        return sql, (params["employee_id"], year)

    sql = """
        SELECT * FROM performance_reviews
        WHERE employee_id = ?
        ORDER BY year, quarter
    """
    return sql, (params["employee_id"],)


def _build_department_members_query(
    params: Mapping[str, Any]
) -> tuple[str, tuple[Any, ...]]:
    sql = """
        SELECT employee_id, name, level, hire_date, email
        FROM employees
        WHERE department = ? AND status = 'active'
        ORDER BY employee_id
    """
    return sql, (params["department"],)


def _build_projects_by_status_query(
    params: Mapping[str, Any]
) -> tuple[str, tuple[Any, ...]]:
    sql = """
        SELECT p.*, e.name AS lead_name
        FROM projects p
        LEFT JOIN employees e ON p.lead_id = e.employee_id
        WHERE p.status = ?
        ORDER BY p.start_date
    """
    return sql, (params["status"],)


def _build_all_projects_query(
    params: Mapping[str, Any]
) -> tuple[str, tuple[Any, ...]]:
    del params
    sql = """
        SELECT p.*, e.name AS lead_name
        FROM projects p
        LEFT JOIN employees e ON p.lead_id = e.employee_id
        ORDER BY p.project_id
    """
    return sql, tuple()


def _build_find_employee_query(params: Mapping[str, Any]) -> tuple[str, tuple[Any, ...]]:
    sql = """
        SELECT e.employee_id, e.name, e.department, e.level,
               e.hire_date, m.name AS manager_name, e.email, e.status
        FROM employees e
        LEFT JOIN employees m ON e.manager_id = m.employee_id
        WHERE e.name LIKE ?
    """
    return sql, (f"%{params['name']}%",)


DEFAULT_CAPABILITIES: tuple[QueryCapability, ...] = (
    QueryCapability(
        name="employee.lookup",
        description="Query active employees with optional filters.",
        sql_builder=_build_employee_query,
    ),
    QueryCapability(
        name="employee.projects",
        description="Query projects for a single employee.",
        sql_builder=_build_employee_projects_query,
    ),
    QueryCapability(
        name="attendance.lookup",
        description="Query attendance records by employee and month.",
        sql_builder=_build_attendance_query,
    ),
    QueryCapability(
        name="performance.lookup",
        description="Query employee performance reviews.",
        sql_builder=_build_performance_query,
    ),
    QueryCapability(
        name="department.members",
        description="Query active department members.",
        sql_builder=_build_department_members_query,
    ),
    QueryCapability(
        name="projects.by_status",
        description="Query projects by status.",
        sql_builder=_build_projects_by_status_query,
    ),
    QueryCapability(
        name="projects.all",
        description="Query all projects.",
        sql_builder=_build_all_projects_query,
    ),
    QueryCapability(
        name="employee.find_by_name",
        description="Fuzzy find employees by name.",
        sql_builder=_build_find_employee_query,
    ),
)


def create_default_capability_registry() -> CapabilityRegistry:
    registry = CapabilityRegistry()
    for capability in DEFAULT_CAPABILITIES:
        registry.register(capability)
    return registry