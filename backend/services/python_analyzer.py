import ast
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from backend.schemas import DiffFile, Finding, ReviewResponse
from backend.services.diff_service import make_unified_patch


RULE_SOURCE = "Python AST rules v1"
SAMPLES_PATH = Path(__file__).resolve().parents[1] / "data" / "python_samples.json"


def load_python_samples() -> list[dict[str, str]]:
    with SAMPLES_PATH.open(encoding="utf-8") as sample_file:
        return json.load(sample_file)


class _RuleVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.findings: list[Finding] = []

    def _add(
        self,
        node: ast.AST,
        *,
        severity: str,
        category: str,
        title: str,
        explanation: str,
        why_it_matters: str,
        recommendation: str,
        suggested_code: str,
    ) -> None:
        self.findings.append(
            Finding(
                id=f"ast-{len(self.findings) + 1}",
                severity=severity,
                category=category,
                title=title,
                file="submitted.py",
                line=getattr(node, "lineno", None),
                explanation=explanation,
                why_it_matters=why_it_matters,
                recommendation=recommendation,
                suggested_code=suggested_code,
                source=RULE_SOURCE,
            )
        )

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_mutable_defaults(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_mutable_defaults(node)
        self.generic_visit(node)

    def _check_mutable_defaults(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        defaults = [*node.args.defaults, *(value for value in node.args.kw_defaults if value is not None)]
        for default in defaults:
            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                self._add(
                    default,
                    severity="Medium",
                    category="Potential bug",
                    title="Mutable default argument is shared between calls",
                    explanation="A list, dictionary, or set is created once when the function is defined and reused on later calls.",
                    why_it_matters="Mutations from one call can unexpectedly affect results from a later call.",
                    recommendation="Use None as the default and create a fresh collection inside the function.",
                    suggested_code="def add_item(item, items=None):\n    if items is None:\n        items = []\n    items.append(item)\n    return items",
                )

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type is None:
            self._add(
                node,
                severity="Medium",
                category="Reliability",
                title="Bare except catches unrelated exceptions",
                explanation="This handler catches every exception, including process-control exceptions such as KeyboardInterrupt.",
                why_it_matters="Unexpected failures can be hidden, making errors harder to diagnose and control flow unpredictable.",
                recommendation="Catch only the exception types this code expects and handle or report them explicitly.",
                suggested_code="except (ValueError, TypeError) as error:\n    logger.warning(\"Invalid input: %s\", error)",
            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        called_name = _call_name(node.func)
        if called_name in {"eval", "exec"}:
            self._add(
                node,
                severity="High",
                category="Security",
                title=f"Dynamic code execution via {called_name}()",
                explanation=f"{called_name}() interprets a string as Python code.",
                why_it_matters="If the string is influenced by an untrusted source, it may execute unintended code. The input flow is not verified by this rule.",
                recommendation="Avoid evaluating code strings. Parse a data format such as JSON or use an explicit allowlist of operations.",
                suggested_code="import json\nvalue = json.loads(untrusted_text)",
            )
        elif called_name in {"pickle.load", "pickle.loads"}:
            self._add(
                node,
                severity="High",
                category="Security",
                title="Pickle deserialization can execute code",
                explanation="The code deserializes data using pickle.",
                why_it_matters="Loading attacker-controlled pickle data can execute code during deserialization; whether this input is trusted is not established here.",
                recommendation="Do not load pickle data from untrusted sources. Use a non-executable format such as JSON for data exchange.",
                suggested_code="import json\nvalue = json.loads(serialized_text)",
            )
        elif _uses_shell_true(node):
            self._add(
                node,
                severity="High",
                category="Security",
                title="Subprocess is started with shell=True",
                explanation="A subprocess call asks Python to interpret a command through a shell.",
                why_it_matters="Shell metacharacters in untrusted command input can change what gets executed; the input flow is not verified by this rule.",
                recommendation="Pass an argument list and keep shell disabled. Validate each argument for its expected format.",
                suggested_code='subprocess.run(["tool", validated_argument], check=True)',
            )
        elif called_name.endswith(".execute") and node.args and _is_dynamic_sql(node.args[0]):
            self._add(
                node.args[0],
                severity="High",
                category="Security",
                title="SQL query is built with string interpolation",
                explanation="A SQL-like string passed to execute() is built through concatenation or an f-string.",
                why_it_matters="If untrusted values are interpolated into the query, they may change its meaning. This rule cannot confirm the source or exploitability.",
                recommendation="Use the database driver's parameterized-query interface instead of constructing SQL with string operations.",
                suggested_code='cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))',
            )
        self.generic_visit(node)


def analyze_python_source(source: str) -> ReviewResponse:
    try:
        tree = ast.parse(source, filename="submitted.py")
    except SyntaxError as error:
        line = error.lineno or 1
        message = (error.msg or "Invalid Python syntax")[:300]
        findings = [
            Finding(
                id="syntax-1",
                severity="High",
                category="Syntax",
                title="Python syntax error",
                file="submitted.py",
                line=line,
                explanation=message,
                why_it_matters="Python cannot parse this source as a module, so the code cannot run in its current form.",
                recommendation="Correct the syntax at the reported line and run the Python parser or your test suite again.",
                source=RULE_SOURCE,
            )
        ]
        summary = f"Python parsing found a syntax error on line {line}."
    else:
        visitor = _RuleVisitor()
        visitor.visit(tree)
        findings = visitor.findings
        if findings:
            summary = f"Python static analysis detected {len(findings)} issue(s) matching the configured AST rules."
        else:
            summary = "No issues were detected by the configured Python AST rules."

    score = max(
        0,
        100
        - sum(
            {"Critical": 35, "High": 25, "Medium": 12, "Low": 5}[finding.severity]
            for finding in findings
        ),
    )
    filename = "submitted.py"
    return ReviewResponse(
        id=str(uuid4()),
        repository="local/python-snippet",
        pull_request_number=1,
        title="Python code review",
        author="local-user",
        branch="local/submitted-code",
        status="Completed",
        summary=summary,
        score=score,
        mode="Python static analysis (AST rules)",
        reviewed_at=datetime.now(timezone.utc).isoformat(),
        files=[DiffFile(filename=filename, old="", new=source, patch=make_unified_patch("", source, filename))],
        findings=findings,
    )


def _call_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _uses_shell_true(node: ast.Call) -> bool:
    return _call_name(node.func).startswith("subprocess.") and any(
        keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True
        for keyword in node.keywords
    )


def _is_dynamic_sql(node: ast.expr) -> bool:
    if isinstance(node, ast.JoinedStr):
        return _contains_sql_keyword(node)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
        return _contains_sql_keyword(node)
    return False


def _contains_sql_keyword(node: ast.AST) -> bool:
    keywords = ("select ", "insert ", "update ", "delete ")
    return any(
        isinstance(part, ast.Constant)
        and isinstance(part.value, str)
        and any(keyword in part.value.lower() for keyword in keywords)
        for part in ast.walk(node)
    )
