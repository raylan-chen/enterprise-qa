"""
知识库检索引擎

基于 BM25 + jieba 中文分词，按 Markdown 二级标题分段索引。
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import jieba
from rank_bm25 import BM25Okapi


@dataclass
class KBSection:
    """A section of a knowledge base document."""

    file_name: str  # e.g. "hr_policies.md"
    file_path: str  # full relative path e.g. "knowledge/hr_policies.md"
    section: str  # section heading e.g. "考勤制度 > 迟到规则"
    content: str  # raw markdown content of this section
    tokens: list[str]  # jieba-tokenized content for BM25


@dataclass
class SearchResult:
    """A search result from the knowledge base."""

    file_name: str
    file_path: str
    section: str
    content: str
    score: float


class KBEngine:
    """Knowledge base search engine using BM25 + jieba."""

    def __init__(self, kb_path: str):
        self._kb_path = kb_path
        self._sections: list[KBSection] = []
        self._bm25: Optional[BM25Okapi] = None
        self._validate_path()
        self._build_index()

    def _validate_path(self) -> None:
        if not Path(self._kb_path).exists():
            raise FileNotFoundError(f"知识库目录不存在: {self._kb_path}")

    def _build_index(self) -> None:
        """Scan all .md files and build BM25 index."""
        self._sections = []
        kb_root = Path(self._kb_path)

        for md_file in sorted(kb_root.rglob("*.md")):
            rel_path = str(md_file.relative_to(kb_root.parent))
            file_name = md_file.name
            content = md_file.read_text(encoding="utf-8")
            sections = self._split_sections(content, file_name, rel_path)
            self._sections.extend(sections)

        if self._sections:
            corpus = [s.tokens for s in self._sections]
            self._bm25 = BM25Okapi(corpus)

    @staticmethod
    def _split_sections(
        content: str, file_name: str, file_path: str
    ) -> list[KBSection]:
        """Split markdown content into sections by ## headings."""
        sections: list[KBSection] = []
        lines = content.split("\n")

        # Track heading hierarchy
        h1_title = ""
        current_heading = ""
        current_lines: list[str] = []

        def _flush():
            if current_lines:
                text = "\n".join(current_lines).strip()
                if text:
                    heading = current_heading or file_name
                    tokens = list(jieba.cut(text))
                    sections.append(
                        KBSection(
                            file_name=file_name,
                            file_path=file_path,
                            section=heading,
                            content=text,
                            tokens=tokens,
                        )
                    )

        for line in lines:
            # Match headings
            h1_match = re.match(r"^#\s+(.+)$", line)
            h2_match = re.match(r"^##\s+(.+)$", line)
            h3_match = re.match(r"^###\s+(.+)$", line)

            if h1_match:
                _flush()
                h1_title = h1_match.group(1).strip()
                current_heading = h1_title
                current_lines = []
            elif h2_match:
                _flush()
                h2_title = h2_match.group(1).strip()
                current_heading = f"{h1_title} > {h2_title}" if h1_title else h2_title
                current_lines = []
            elif h3_match:
                _flush()
                h3_title = h3_match.group(1).strip()
                if h1_title:
                    # Keep parent context in heading
                    current_heading = f"{h1_title} > {current_heading.split(' > ')[-1]} > {h3_title}" if " > " in current_heading else f"{h1_title} > {h3_title}"
                else:
                    current_heading = h3_title
                current_lines = []
            else:
                current_lines.append(line)

        _flush()
        return sections

    def search(self, query: str, top_k: int = 3) -> list[SearchResult]:
        """
        Search the knowledge base using BM25.

        Args:
            query: Natural language query string.
            top_k: Maximum number of results to return.

        Returns:
            List of SearchResult sorted by relevance (highest first).
        """
        if not self._bm25 or not self._sections:
            return []

        query_tokens = list(jieba.cut(query))
        scores = self._bm25.get_scores(query_tokens)

        # Pair sections with scores and sort
        scored = sorted(
            zip(self._sections, scores), key=lambda x: x[1], reverse=True
        )

        results: list[SearchResult] = []
        for section, score in scored[:top_k]:
            if score > 0:
                results.append(
                    SearchResult(
                        file_name=section.file_name,
                        file_path=section.file_path,
                        section=section.section,
                        content=section.content,
                        score=round(float(score), 4),
                    )
                )

        return results

    def get_document_list(self) -> list[dict[str, str]]:
        """Return list of indexed documents with metadata."""
        seen: dict[str, dict] = {}
        for s in self._sections:
            if s.file_name not in seen:
                seen[s.file_name] = {
                    "file_name": s.file_name,
                    "file_path": s.file_path,
                    "sections": [],
                }
            seen[s.file_name]["sections"].append(s.section)
        return list(seen.values())

    @property
    def section_count(self) -> int:
        return len(self._sections)
