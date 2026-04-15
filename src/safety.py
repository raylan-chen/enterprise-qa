"""
安全层模块

提供 SQL 注入检测、输入验证和只读查询限制。
"""

from __future__ import annotations

import re

# ---- SQL injection patterns ----
_INJECTION_PATTERNS: list[re.Pattern] = [
    # Tautologies: '1'='1', 'a'='a', OR 1=1, etc.
    re.compile(r"'[^']*'\s*=\s*'[^']*'", re.IGNORECASE),       # WHERE '1'='1'
    re.compile(r"'\s*=\s*'", re.IGNORECASE),                     # '='  (partial tautology)
    re.compile(r"\bOR\s+\d+\s*=\s*\d+", re.IGNORECASE),         # OR 1=1
    re.compile(r"\bOR\s+'[^']*'\s*=\s*'", re.IGNORECASE),       # OR 'x'='
    # Comments
    re.compile(r"(--|#|/\*)", re.IGNORECASE),
    # Dangerous keywords
    re.compile(r"\b(UNION\s+(ALL\s+)?SELECT)\b", re.IGNORECASE),
    re.compile(r"\b(DROP\s+TABLE)\b", re.IGNORECASE),
    re.compile(r"\b(INSERT\s+INTO)\b", re.IGNORECASE),
    re.compile(r"\b(UPDATE\s+\w+\s+SET)\b", re.IGNORECASE),
    re.compile(r"\b(DELETE\s+FROM)\b", re.IGNORECASE),
    re.compile(r"\b(ALTER\s+TABLE)\b", re.IGNORECASE),
    re.compile(r"\b(CREATE\s+TABLE)\b", re.IGNORECASE),
    re.compile(r"\b(EXEC(UTE)?)\b", re.IGNORECASE),
    re.compile(r"\b(xp_|sp_)\w+", re.IGNORECASE),
    re.compile(r";\s*(DROP|DELETE|INSERT|UPDATE|ALTER|CREATE)", re.IGNORECASE),
    re.compile(r"'\s*;\s*", re.IGNORECASE),
]

# Allowed SQL: only SELECT / PRAGMA / EXPLAIN / WITH
_ALLOWED_SQL_START = re.compile(
    r"^\s*(SELECT|PRAGMA|EXPLAIN|WITH)\b", re.IGNORECASE
)

MAX_INPUT_LENGTH = 2000


def detect_sql_injection(text: str) -> tuple[bool, str]:
    """
    Check if the input text contains SQL injection patterns.

    Returns:
        (is_safe, message): True if safe, False with explanation if injection detected.
    """
    if not text or not text.strip():
        return True, ""

    for pattern in _INJECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            return False, f"检测到潜在的 SQL 注入模式: {match.group()}"

    return True, ""


def is_readonly_sql(sql: str) -> tuple[bool, str]:
    """
    Verify that a SQL statement is read-only (SELECT / PRAGMA / EXPLAIN / WITH).

    Returns:
        (is_readonly, message)
    """
    stripped = sql.strip()
    if not stripped:
        return False, "SQL 语句为空"

    if _ALLOWED_SQL_START.match(stripped):
        # Double-check: no write statements embedded
        write_patterns = [
            r"\b(INSERT\s+INTO)\b",
            r"\b(UPDATE\s+\w+\s+SET)\b",
            r"\b(DELETE\s+FROM)\b",
            r"\b(DROP\s+)\b",
            r"\b(ALTER\s+)\b",
            r"\b(CREATE\s+)\b",
        ]
        for wp in write_patterns:
            if re.search(wp, stripped, re.IGNORECASE):
                return False, f"SQL 语句包含写操作"
        return True, ""

    return False, "仅允许 SELECT / PRAGMA / EXPLAIN / WITH 查询"


def validate_input(text: str) -> tuple[bool, str]:
    """
    Validate user input for length and basic sanity.

    Returns:
        (is_valid, message)
    """
    if not text or not text.strip():
        return False, "输入不能为空"

    if len(text) > MAX_INPUT_LENGTH:
        return False, f"输入长度超出限制（最大 {MAX_INPUT_LENGTH} 字符）"

    # Check for SQL injection in natural language input
    safe, msg = detect_sql_injection(text)
    if not safe:
        return False, msg

    return True, ""


def sanitize_for_display(text: str) -> str:
    """Sanitize text for safe display (strip control chars)."""
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
