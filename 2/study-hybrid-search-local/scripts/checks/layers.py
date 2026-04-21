from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Violation:
    file_path: Path
    line: int
    import_name: str
    message: str


@dataclass(frozen=True)
class Rule:
    name: str
    target_dir: Path
    allowed_prefixes: tuple[str, ...]
    blocked_prefixes: tuple[str, ...] = ()


def _is_stdlib_module(module_name: str) -> bool:
    root = module_name.split(".", 1)[0]
    if root == "__future__":
        return True
    return root in sys.stdlib_module_names


def _iter_python_files(base_dir: Path) -> list[Path]:
    if not base_dir.exists():
        return []
    return sorted(p for p in base_dir.rglob("*.py") if "__pycache__" not in p.parts)


def _extract_imports(tree: ast.AST) -> list[tuple[int, str]]:
    imports: list[tuple[int, str]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.level and not node.module:
                continue
            module = node.module or ""
            imports.append((node.lineno, module))

    return imports


def _is_allowed(import_name: str, allowed_prefixes: tuple[str, ...]) -> bool:
    if import_name == "":
        return True
    if _is_stdlib_module(import_name):
        return True
    return any(import_name == p or import_name.startswith(f"{p}.") for p in allowed_prefixes)


def _is_blocked(import_name: str, blocked_prefixes: tuple[str, ...]) -> bool:
    return any(import_name == p or import_name.startswith(f"{p}.") for p in blocked_prefixes)


def _check_rule(rule: Rule) -> list[Violation]:
    violations: list[Violation] = []

    for file_path in _iter_python_files(rule.target_dir):
        rel_path = file_path.relative_to(ROOT)
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))

        for line, import_name in _extract_imports(tree):
            if _is_blocked(import_name, rule.blocked_prefixes):
                violations.append(
                    Violation(
                        file_path=rel_path,
                        line=line,
                        import_name=import_name,
                        message=f"blocked import for {rule.name}",
                    )
                )
                continue

            if not _is_allowed(import_name, rule.allowed_prefixes):
                violations.append(
                    Violation(
                        file_path=rel_path,
                        line=line,
                        import_name=import_name,
                        message=f"import not allowed for {rule.name}",
                    )
                )

    return violations


def _rules_for_stage(stage: int) -> list[Rule]:
    rules = [
        Rule(
            name="application-usecases",
            target_dir=ROOT / "pipelines" / "src" / "pipelines" / "application",
            allowed_prefixes=("pipelines.application", "common.ports", "common.dtos"),
        ),
    ]

    if stage >= 2:
        rules.append(
            Rule(
                name="api-routes",
                target_dir=ROOT / "app" / "src" / "app" / "routes",
                allowed_prefixes=(
                    "app",
                    "pipelines.application",
                    "common.core",
                    "common.ports",
                    "fastapi",
                    "httpx",
                ),
                blocked_prefixes=("pipelines.repositories", "common.clients", "pipelines.adapters"),
            )
        )

    if stage >= 3:
        rules.append(
            Rule(
                name="ports",
                target_dir=ROOT / "common" / "src" / "common" / "ports",
                allowed_prefixes=("common.ports", "common.dtos"),
                blocked_prefixes=("pipelines.adapters", "common.clients", "pipelines.repositories", "app", "fastapi", "pydantic"),
            )
        )

    if stage >= 4:
        rules.extend(
            [
                Rule(
                    name="jobs",
                    target_dir=ROOT / "jobs" / "src" / "jobs",
                    allowed_prefixes=(
                        "jobs",
                        "common.core",
                        "common.clients",
                        "pipelines.repositories",
                        "pipelines.services",
                        "psycopg",
                    ),
                    blocked_prefixes=(
                        "app",
                        "pipelines.application",
                        "common.ports.inbound",
                        "train",
                        "embed",
                        "sync",
                    ),
                ),
                Rule(
                    name="ml.sync",
                    target_dir=ROOT / "ml" / "sync" / "src" / "sync",
                    allowed_prefixes=(
                        "sync",
                        "common.core",
                        "common.clients",
                        "psycopg",
                    ),
                    blocked_prefixes=(
                        "app",
                        "pipelines.application",
                        "common.ports.inbound",
                        "embed",
                        "train",
                    ),
                ),
                Rule(
                    name="ml.embed",
                    target_dir=ROOT / "ml" / "embed" / "src" / "embed",
                    allowed_prefixes=(
                        "embed",
                        "common.core",
                        "common.clients",
                        "pipelines.repositories",
                        "pipelines.services",
                        "psycopg",
                    ),
                    blocked_prefixes=(
                        "app",
                        "pipelines.application",
                        "common.ports.inbound",
                        "train",
                        "sync",
                    ),
                ),
                Rule(
                    name="ml.train",
                    target_dir=ROOT / "ml" / "train" / "src" / "train",
                    allowed_prefixes=(
                        "train",
                        "common.core",
                        "pipelines.repositories",
                        "psycopg",
                        "numpy",
                        "lightgbm",
                    ),
                    blocked_prefixes=(
                        "app",
                        "pipelines.application",
                        "pipelines.adapters",
                        "common.ports.inbound",
                        "embed",
                        "sync",
                    ),
                ),
            ]
        )

    if stage >= 5:
        rules.append(
            Rule(
                name="adapters-outbound",
                target_dir=ROOT / "pipelines" / "src" / "pipelines" / "adapters",
                allowed_prefixes=("pipelines.adapters", "common.ports", "common.clients", "pipelines.repositories", "pipelines.services", "common.core", "redis"),
                blocked_prefixes=("app", "pipelines.application"),
            )
        )

    return rules


def main() -> int:
    parser = argparse.ArgumentParser(description="Layer boundary checks with Python AST")
    parser.add_argument("--stage", type=int, choices=(1, 2, 3, 4, 5), default=1, help="Rule stage to enforce")
    args = parser.parse_args()

    violations: list[Violation] = []
    for rule in _rules_for_stage(args.stage):
        violations.extend(_check_rule(rule))

    if not violations:
        print(f"[check-layers] OK (stage={args.stage})")
        return 0

    print(f"[check-layers] FAILED (stage={args.stage})")
    for v in violations:
        print(f"- {v.file_path}:{v.line}: {v.import_name} -> {v.message}")
    print(f"Total violations: {len(violations)}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
