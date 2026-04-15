"""
CLI 统一入口

提供子命令: schema, db-query, kb-search, db-employee, db-projects, db-attendance, db-performance
输出 JSON 格式，供 Claude Code 自定义命令调用。
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

# Force UTF-8 stdout on Windows to avoid encoding issues with Chinese characters
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Ensure parent dir is on path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_config
from src.db_engine import DBEngine, format_query_result, strip_sensitive_fields
from src.kb_engine import KBEngine
from src.safety import validate_input, detect_sql_injection, is_readonly_sql


def _json_out(data: dict) -> None:
    """Print JSON to stdout."""
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def cmd_schema(args: argparse.Namespace, cfg) -> None:
    """Output database schema information."""
    db = DBEngine(cfg.db_path)
    _json_out({"schema": db.get_schema_info()})


def cmd_db_query(args: argparse.Namespace, cfg) -> None:
    """Execute a safe SQL query."""
    sql = args.sql

    # Validate SQL safety
    ok, msg = is_readonly_sql(sql)
    if not ok:
        _json_out({"error": msg})
        sys.exit(1)

    injection_safe, inj_msg = detect_sql_injection(sql)
    if not injection_safe:
        _json_out({"error": inj_msg})
        sys.exit(1)

    params = tuple()
    if args.params:
        params = tuple(json.loads(args.params))

    db = DBEngine(cfg.db_path)
    result = db.execute_query(sql, params)
    _json_out(strip_sensitive_fields(result))


def cmd_kb_search(args: argparse.Namespace, cfg) -> None:
    """Search knowledge base."""
    query = args.query
    ok, msg = validate_input(query)
    if not ok:
        _json_out({"error": msg})
        sys.exit(1)

    kb = KBEngine(cfg.kb_path)
    results = kb.search(query, top_k=args.top_k)
    _json_out({
        "query": query,
        "results": [
            {
                "file_name": r.file_name,
                "file_path": r.file_path,
                "section": r.section,
                "content": r.content,
                "score": r.score,
            }
            for r in results
        ],
        "total": len(results),
    })


def cmd_db_employee(args: argparse.Namespace, cfg) -> None:
    """Query employee information."""
    db = DBEngine(cfg.db_path)
    result = db.query_employee(
        name=args.name,
        employee_id=args.employee_id,
        department=args.department,
    )
    _json_out(strip_sensitive_fields(result))


def cmd_db_projects(args: argparse.Namespace, cfg) -> None:
    """Query employee projects or projects by status."""
    db = DBEngine(cfg.db_path)
    if args.employee_id:
        result = db.query_employee_projects(args.employee_id)
    elif args.status:
        result = db.query_projects_by_status(args.status)
    else:
        result = db.execute_query("SELECT p.*, e.name AS lead_name FROM projects p LEFT JOIN employees e ON p.lead_id = e.employee_id ORDER BY p.project_id")
    _json_out(strip_sensitive_fields(result))


def cmd_db_attendance(args: argparse.Namespace, cfg) -> None:
    """Query attendance records."""
    db = DBEngine(cfg.db_path)
    result = db.query_attendance(
        employee_id=args.employee_id,
        year=args.year,
        month=args.month,
        status_filter=args.status,
    )
    _json_out(strip_sensitive_fields(result))


def cmd_db_performance(args: argparse.Namespace, cfg) -> None:
    """Query performance reviews."""
    db = DBEngine(cfg.db_path)
    result = db.query_performance(
        employee_id=args.employee_id,
        year=args.year,
    )
    _json_out(strip_sensitive_fields(result))


def cmd_db_department(args: argparse.Namespace, cfg) -> None:
    """Query department members."""
    db = DBEngine(cfg.db_path)
    result = db.query_department_members(args.department)
    _json_out(strip_sensitive_fields(result))


def cmd_kb_list(args: argparse.Namespace, cfg) -> None:
    """List knowledge base documents."""
    kb = KBEngine(cfg.kb_path)
    docs = kb.get_document_list()
    _json_out({"documents": docs, "total_sections": kb.section_count})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="企业智能问答助手 - CLI 工具",
        prog="enterprise-qa",
    )
    parser.add_argument(
        "--config", type=str, default=None, help="配置文件路径"
    )
    parser.add_argument(
        "--base-dir", type=str, default=None, help="基准目录路径"
    )

    sub = parser.add_subparsers(dest="command", help="子命令")

    # schema
    sub.add_parser("schema", help="输出数据库表结构")

    # db-query
    p_dbq = sub.add_parser("db-query", help="执行 SQL 查询")
    p_dbq.add_argument("--sql", required=True, help="SQL SELECT 语句（使用 ? 占位符）")
    p_dbq.add_argument("--params", default=None, help="参数列表（JSON 数组格式）")

    # kb-search
    p_kbs = sub.add_parser("kb-search", help="知识库检索")
    p_kbs.add_argument("--query", required=True, help="搜索关键词")
    p_kbs.add_argument("--top-k", type=int, default=3, help="返回结果数")

    # kb-list
    sub.add_parser("kb-list", help="列出知识库文档")

    # db-employee
    p_emp = sub.add_parser("db-employee", help="查询员工信息")
    p_emp.add_argument("--name", default=None, help="员工姓名")
    p_emp.add_argument("--employee-id", default=None, help="员工 ID")
    p_emp.add_argument("--department", default=None, help="部门名称")

    # db-projects
    p_prj = sub.add_parser("db-projects", help="查询项目信息")
    p_prj.add_argument("--employee-id", default=None, help="员工 ID")
    p_prj.add_argument("--status", default=None, help="项目状态")

    # db-attendance
    p_att = sub.add_parser("db-attendance", help="查询考勤记录")
    p_att.add_argument("--employee-id", required=True, help="员工 ID")
    p_att.add_argument("--year", type=int, required=True, help="年份")
    p_att.add_argument("--month", type=int, required=True, help="月份")
    p_att.add_argument("--status", default=None, help="考勤状态过滤")

    # db-performance
    p_perf = sub.add_parser("db-performance", help="查询绩效记录")
    p_perf.add_argument("--employee-id", required=True, help="员工 ID")
    p_perf.add_argument("--year", type=int, default=None, help="年份")

    # db-department
    p_dept = sub.add_parser("db-department", help="查询部门成员")
    p_dept.add_argument("--department", required=True, help="部门名称")

    return parser


_CMD_MAP = {
    "schema": cmd_schema,
    "db-query": cmd_db_query,
    "kb-search": cmd_kb_search,
    "kb-list": cmd_kb_list,
    "db-employee": cmd_db_employee,
    "db-projects": cmd_db_projects,
    "db-attendance": cmd_db_attendance,
    "db-performance": cmd_db_performance,
    "db-department": cmd_db_department,
}


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Load config
    cfg = load_config(
        config_path=args.config,
        base_dir=args.base_dir,
    )

    handler = _CMD_MAP.get(args.command)
    if handler:
        handler(args, cfg)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
