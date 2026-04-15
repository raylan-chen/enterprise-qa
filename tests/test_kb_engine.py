"""Tests for kb_engine module."""

import pytest
from pathlib import Path

from src.kb_engine import KBEngine, KBSection

# Path to the test knowledge base
KB_PATH = str(
    Path(__file__).resolve().parent.parent
    / "data"
    / "knowledge"
)


@pytest.fixture
def kb():
    return KBEngine(KB_PATH)


class TestKBEngine:
    """Test knowledge base engine."""

    def test_init_valid_path(self, kb):
        assert kb.section_count > 0

    def test_init_invalid_path(self):
        with pytest.raises(FileNotFoundError):
            KBEngine("/nonexistent/path")

    def test_document_list(self, kb):
        docs = kb.get_document_list()
        file_names = {d["file_name"] for d in docs}
        assert "hr_policies.md" in file_names
        assert "promotion_rules.md" in file_names
        assert "faq.md" in file_names
        assert "finance_rules.md" in file_names
        assert "tech_docs.md" in file_names

    def test_search_annual_leave(self, kb):
        """T03: 年假怎么计算."""
        results = kb.search("年假怎么计算")
        assert len(results) > 0
        # Should find relevant content
        top = results[0]
        assert "年假" in top.content or "年假" in top.section
        assert "5 天" in top.content or "5天" in top.content

    def test_search_late_penalty(self, kb):
        """T04: 迟到几次扣钱."""
        results = kb.search("迟到几次扣钱")
        assert len(results) > 0
        top = results[0]
        assert "迟到" in top.content or "迟到" in top.section
        assert "50" in top.content

    def test_search_promotion_p5_p6(self, kb):
        """Should find P5→P6 promotion rules."""
        results = kb.search("P5晋升P6条件")
        assert len(results) > 0
        found = any("P5" in r.content and "P6" in r.content for r in results)
        assert found

    def test_search_reimbursement(self, kb):
        """差旅费报销标准."""
        results = kb.search("差旅费报销标准")
        assert len(results) > 0
        found = any("报销" in r.content or "差旅" in r.content for r in results)
        assert found

    def test_search_meeting_notes(self, kb):
        """全员大会内容."""
        results = kb.search("全员大会 营收")
        assert len(results) > 0
        found = any("150%" in r.content or "营收" in r.content for r in results)
        assert found

    def test_search_no_results(self, kb):
        """Completely irrelevant query should return low/no score results."""
        results = kb.search("xyzabc123随机无意义字符串")
        # BM25 may still return some results due to partial token matches
        # Key point: results are far less relevant than actual matches
        if results:
            assert results[0].score < 5.0

    def test_search_top_k(self, kb):
        results = kb.search("年假", top_k=1)
        assert len(results) <= 1

    def test_search_results_have_source(self, kb):
        results = kb.search("考勤制度")
        for r in results:
            assert r.file_name
            assert r.file_path
            assert r.section


class TestKBSectionSplit:
    def test_split_produces_sections(self, kb):
        """Should produce multiple sections from documents."""
        assert kb.section_count > 10

    def test_sections_have_hierarchy(self, kb):
        """Sections should have hierarchical headings with >."""
        docs = kb.get_document_list()
        for doc in docs:
            sections_with_hierarchy = [
                s for s in doc["sections"] if " > " in s
            ]
            # At least some sections should have hierarchy
            if doc["file_name"] != "faq.md":
                assert len(sections_with_hierarchy) > 0, (
                    f"{doc['file_name']} should have hierarchical sections"
                )
