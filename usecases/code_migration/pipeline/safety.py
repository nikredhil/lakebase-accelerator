"""Static safety guard for generated PySpark before it is executed.

The pipeline runs LLM/rule-generated code via exec()/cluster execution. This
guard parses the module and rejects anything outside a narrow allowlist so a bad
(or prompt-injected) conversion can't read files, hit the network, or escape the
intended `transform(spark)` contract. Violations raise UnsafeCodeError, which the
orchestrator treats as a failed validation (-> retry / learn), never as a run.
"""
from __future__ import annotations

import ast

# Imports may only come from these roots: PySpark + a few pure, side-effect-free
# stdlib modules a transform might legitimately use. No os/sys/subprocess/socket/
# importlib/requests/etc. (no file, network, or code-exec capability).
ALLOWED_IMPORT_ROOTS = {
    "pyspark", "datetime", "decimal", "math", "re", "json",
    "functools", "itertools", "typing", "collections",
}

# Builtins that enable code execution, I/O, or introspection escapes.
DENIED_CALL_NAMES = {
    "exec", "eval", "compile", "__import__", "open", "input", "breakpoint",
    "globals", "locals", "vars", "getattr", "setattr", "delattr",
    "memoryview", "exit", "quit", "help",
}


class UnsafeCodeError(ValueError):
    """Raised when converted code violates the safety allowlist."""


def validate_transform_code(code: str) -> None:
    """Raise UnsafeCodeError if `code` is unsafe or doesn't define transform(spark)."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise UnsafeCodeError(f"syntax error: {e}") from e

    violations: set[str] = set()
    transform_ok = False

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "transform":
            args = node.args.posonlyargs + node.args.args
            if len(args) >= 1:
                transform_ok = True

        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in ALLOWED_IMPORT_ROOTS:
                    violations.add(f"disallowed import: {alias.name}")

        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root not in ALLOWED_IMPORT_ROOTS:
                violations.add(f"disallowed import from: {node.module}")

        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in DENIED_CALL_NAMES:
                violations.add(f"disallowed call: {node.func.id}()")

        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__") and node.attr.endswith("__"):
                violations.add(f"disallowed dunder access: .{node.attr}")

    if not transform_ok:
        violations.add("must define transform(spark) taking at least one argument")

    if violations:
        raise UnsafeCodeError("; ".join(sorted(violations)))
