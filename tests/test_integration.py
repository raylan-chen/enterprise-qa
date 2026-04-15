"""
Integration tests — covering all T01-T12 test cases from the exam.

These tests verify the full pipeline: CLI invocation → engine → result correctness.
"""

import json
import subprocess
import sys
import pytest
from pathlib import Path

BASE_DIR = str(
    Path(__file__).resolve().parent.parent
)
SRC_MAIN = str(Path(__file__).resolve().parent.parent / "src" / "main.py")
PYTHON = sys.executable


def run_cli(*args: str) -> dict:
    """Run the CLI and return parsed JSON output."""
    cmd = [PYTHON, SRC_MAIN, "--base-dir", BASE_DIR] + list(args)
    env = {**__import__('os').environ, "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run(
        cmd,
        capture_output=True,
        cwd=str(Path(__file__).resolve().parent.parent),
        env=env,
    )
    stdout = result.stdout.decode("utf-8", errors="replace")
    stderr = result.stderr.decode("utf-8", errors="replace")
    if result.returncode != 0 and stdout.strip():
        return json.loads(stdout)
    if result.returncode != 0:
        return {"error": stderr.strip(), "_returncode": result.returncode}
    return json.loads(stdout)


# ============================================================================
# T01-T04: 基础查询
# ============================================================================


class TestBasicQueries:
    """T01-T04: Basic database and knowledge base queries."""

    def test_t01_zhang_department(self):
        """T01: 张三的部门是什么？→ 研发部"""
        result = run_cli("db-employee", "--name", "张三")
        assert result["row_count"] == 1
        assert result["rows"][0]["department"] == "研发部"

    def test_t02_li_manager(self):
        """T02: 李四的上级是谁？→ CEO — via manager_name, NOT manager_id"""
        result = run_cli("db-employee", "--name", "李四")
        assert result["row_count"] == 1
        row = result["rows"][0]
        # Sensitive field must not be exposed
        assert "manager_id" not in row
        # Manager name is resolved via JOIN
        assert row["manager_name"] == "CEO"

    def test_t03_annual_leave(self):
        """T03: 年假怎么计算？→ 满1年5天，每年+1，上限15天"""
        result = run_cli("kb-search", "--query", "年假怎么计算")
        assert result["total"] > 0
        content = result["results"][0]["content"]
        assert "5" in content
        assert "15" in content

    def test_t04_late_penalty(self):
        """T04: 迟到几次扣钱？→ 4-6次开始扣，50元/次"""
        result = run_cli("kb-search", "--query", "迟到几次扣钱")
        assert result["total"] > 0
        content = result["results"][0]["content"]
        assert "50" in content


# ============================================================================
# T05-T08: 关联查询
# ============================================================================


class TestAssociatedQueries:
    """T05-T08: Cross-table and mixed queries."""

    def test_t05_zhang_projects(self):
        """T05: 张三负责哪些项目？→ 4个项目"""
        # First get employee ID
        emp = run_cli("db-employee", "--name", "张三")
        eid = emp["rows"][0]["employee_id"]
        assert eid == "EMP-001"
        # Query projects
        result = run_cli("db-projects", "--employee-id", eid)
        assert result["row_count"] == 4
        roles = {r["role"] for r in result["rows"]}
        assert "lead" in roles

    def test_t06_rd_department_count(self):
        """T06: 研发部有多少人？→ 4人"""
        result = run_cli("db-department", "--department", "研发部")
        assert result["row_count"] == 4
        names = {r["name"] for r in result["rows"]}
        assert names == {"张三", "李四", "钱七", "周九"}

    def test_t07_wang_promotion(self):
        """T07: 王五符合P5晋升P6条件吗？→ 不符合（KPI<85, 项目<3）"""
        # Step 1: Get Wang Wu's info
        emp = run_cli("db-employee", "--name", "王五")
        assert emp["row_count"] == 1
        row = emp["rows"][0]
        assert row["level"] == "P5"
        eid = row["employee_id"]

        # Step 2: Check KPI
        perf = run_cli("db-performance", "--employee-id", eid, "--year", "2025")
        scores = [r["kpi_score"] for r in perf["rows"]]
        avg_kpi = sum(scores) / len(scores) if scores else 0
        assert avg_kpi < 85  # Does NOT meet ≥85 requirement

        # Step 3: Check project count
        proj = run_cli("db-projects", "--employee-id", eid)
        assert proj["row_count"] < 3  # Does NOT meet ≥3 requirement

        # Step 4: Get promotion rules
        kb = run_cli("kb-search", "--query", "P5晋升P6条件")
        assert kb["total"] > 0
        assert any("KPI" in r["content"] or "85" in r["content"] for r in kb["results"])

    def test_t08_zhang_feb_late(self):
        """T08: 张三2月迟到几次？→ 2次"""
        result = run_cli(
            "db-attendance",
            "--employee-id", "EMP-001",
            "--year", "2026",
            "--month", "2",
            "--status", "late",
        )
        assert result["row_count"] == 2


# ============================================================================
# T09-T12: 边界情况
# ============================================================================


class TestEdgeCases:
    """T09-T12: Boundary and security cases."""

    def test_t09_nonexistent_employee(self):
        """T09: 查一下EMP-999 → 无此员工"""
        result = run_cli("db-employee", "--employee-id", "EMP-999")
        assert result["row_count"] == 0

    def test_t10_vague_query_kb(self):
        """T10: 最近有什么事？→ 返回会议/项目信息"""
        result = run_cli("kb-search", "--query", "最近有什么事")
        # Should return some results from meeting notes
        assert result["total"] > 0

    def test_t11_sql_injection(self):
        """T11: SQL injection attempt → rejected"""
        result = run_cli(
            "db-query",
            "--sql", "SELECT * FROM users WHERE '1'='1'",
        )
        # Should be caught by safety layer (tautology pattern '1'='1')
        assert "error" in result

    def test_t11_sql_injection_drop(self):
        """SQL injection with DROP should be blocked."""
        result = run_cli(
            "db-query",
            "--sql", "DROP TABLE employees",
        )
        assert "error" in result

    def test_t12_nonsense_query(self):
        """T12: xyzabc123怎么报销 → 无相关信息"""
        result = run_cli("kb-search", "--query", "xyzabc123怎么报销")
        # Either no results or results with low relevance
        if result["total"] > 0:
            # Results should have low relevance compared to normal queries
            assert result["results"][0]["score"] < 8.0


# ============================================================================
# Additional generalization queries
# ============================================================================


class TestGeneralization:
    """Additional queries for generalization capability."""

    def test_li_email(self):
        """李四的邮箱 → lisi@company.com"""
        result = run_cli("db-employee", "--name", "李四")
        assert result["rows"][0]["email"] == "lisi@company.com"

    def test_product_dept_count(self):
        """产品部有多少人 → 3"""
        result = run_cli("db-department", "--department", "产品部")
        assert result["row_count"] == 3

    def test_active_projects(self):
        """有哪些在研项目 → PRJ-001, PRJ-003"""
        result = run_cli("db-projects", "--status", "active")
        assert result["row_count"] == 2
        ids = {r["project_id"] for r in result["rows"]}
        assert ids == {"PRJ-001", "PRJ-003"}

    def test_zhang_performance_2025(self):
        """张三2025年绩效 → 平均89.25"""
        result = run_cli(
            "db-performance", "--employee-id", "EMP-001", "--year", "2025"
        )
        assert result["row_count"] == 4
        scores = [r["kpi_score"] for r in result["rows"]]
        avg = sum(scores) / len(scores)
        assert abs(avg - 89.25) < 0.01

    def test_reimbursement_standard(self):
        """差旅费报销标准"""
        result = run_cli("kb-search", "--query", "差旅费报销标准", "--top-k", "5")
        assert result["total"] > 0
        all_content = " ".join(r["content"] for r in result["results"])
        assert "报销" in all_content

    def test_march_allhands(self):
        """3月全员大会说了什么"""
        result = run_cli("kb-search", "--query", "全员大会", "--top-k", "5")
        assert result["total"] > 0
        all_content = " ".join(r["content"] for r in result["results"])
        all_sections = " ".join(r["section"] for r in result["results"])
        # Should return meeting-related content
        assert "会" in all_content or "会" in all_sections
