"""Enforces the layer-dependency rule from docs/architecture.md §3:

  apps/api  -> agents, core, integrations
  agents    -> core, integrations
  core      -> (stdlib + infra libs only; never imports agents or apps)
  integrations -> core interfaces only
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN: dict[str, set[str]] = {
    "core": {"apps", "agents", "integrations"},
    "agents": {"apps"},
    "integrations": {"apps", "agents"},
}


def _py_files(package: str) -> list[Path]:
    return sorted((ROOT / package).rglob("*.py"))


def _imported_modules(tree: ast.AST) -> list[str]:
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


def test_packages_exist():
    for package in ("core", "agents", "integrations", "apps"):
        assert (ROOT / package / "__init__.py").exists(), f"missing package {package}"


def test_layers_do_not_import_upward():
    violations: list[str] = []
    for package, banned in FORBIDDEN.items():
        files = _py_files(package)
        assert files, f"no python files under {package}/"
        for path in files:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for module in _imported_modules(tree):
                top = module.split(".")[0]
                if top in banned:
                    violations.append(f"{path.relative_to(ROOT)} -> {module}")
    assert not violations, "layer violations:\n" + "\n".join(violations)


def test_no_dynamic_code_execution():
    """JARVIS must never eval/exec arbitrary code (architecture.md §5)."""
    banned_calls = {"eval", "exec", "compile", "__import__"}
    offenders: list[str] = []
    for package in ("core", "apps", "agents", "integrations"):
        for path in _py_files(package):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id in banned_calls
                ):
                    offenders.append(f"{path.relative_to(ROOT)}:{node.lineno} {node.func.id}()")
    assert not offenders, "dynamic code execution found:\n" + "\n".join(offenders)
