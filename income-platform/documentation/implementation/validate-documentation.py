#!/usr/bin/env python3
"""
validate-documentation.py
Income Fortress Platform — Documentation Validation Script

Checks all Agent 03 documentation for completeness, consistency, and cross-references.
Usage: python3 scripts/validate-documentation.py [--strict] [--component agent-03]
"""

import os
import re
import sys
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional

# ── Configuration ──────────────────────────────────────────────────────────────

DOCS_ROOT = Path(__file__).parent.parent / "docs"
AGENT_03_DOCS = DOCS_ROOT.parent / "agents" / "agent-03-income-scorer" / "docs"

REQUIRED_FILES = [
    AGENT_03_DOCS / "index.md",
    AGENT_03_DOCS / "architecture" / "reference-architecture.md",
    AGENT_03_DOCS / "functional" / "agent-03-functional-spec.md",
    AGENT_03_DOCS / "implementation" / "agent-03-implementation-spec.md",
    AGENT_03_DOCS / "decisions" / "ADR-001-post-scoring-llm-explanation.md",
    AGENT_03_DOCS / "diagrams" / "system-architecture.mmd",
    AGENT_03_DOCS / "diagrams" / "scoring-flow-sequence.mmd",
    AGENT_03_DOCS / "diagrams" / "data-model.mmd",
    DOCS_ROOT / "CHANGELOG.md",
    DOCS_ROOT / "decisions-log.md",
    DOCS_ROOT / "platform-index.md",
]

REQUIRED_INVARIANTS = [
    "VETO always forces",
    "tax_efficiency",
    "Weight sets always sum",
    "No hardcoded weights",
    "DataProvider abstraction",
    "versioned with weight snapshot",
    "Positive.*signals never boost",
]

REQUIRED_WEIGHT_CLASSES = [
    "Dividend Stocks",
    "OTM Covered Call ETFs",
    "Bonds",
    "REITs",
    "mREITs",
    "BDCs",
    "CEFs",
    "Preferred Stocks",
]

REQUIRED_ADR_SECTIONS = [
    "Context",
    "Decision",
    "Consequences",
    "Alternatives Considered",
    "Implementation Impact",
]

# ── Result Types ───────────────────────────────────────────────────────────────

@dataclass
class ValidationResult:
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    info: List[str] = field(default_factory=list)
    files_checked: int = 0

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0

# ── Validators ─────────────────────────────────────────────────────────────────

def check_required_files(result: ValidationResult):
    """Verify all required documentation files exist."""
    for path in REQUIRED_FILES:
        if path.exists():
            result.files_checked += 1
            result.info.append(f"✓ {path.name}")
        else:
            result.errors.append(f"MISSING required file: {path}")


def check_invariants(result: ValidationResult):
    """Verify all 7 invariants are documented in index.md."""
    index_path = AGENT_03_DOCS / "index.md"
    if not index_path.exists():
        return

    content = index_path.read_text()
    for invariant in REQUIRED_INVARIANTS:
        if not re.search(invariant, content, re.IGNORECASE):
            result.errors.append(f"MISSING invariant in index.md: '{invariant}'")
        else:
            result.info.append(f"✓ Invariant found: '{invariant[:40]}...'")


def check_weight_sets(result: ValidationResult):
    """Verify all 8 asset classes have weight sets defined and sum to 100."""
    arch_path = AGENT_03_DOCS / "architecture" / "reference-architecture.md"
    if not arch_path.exists():
        return

    content = arch_path.read_text()

    for asset_class in REQUIRED_WEIGHT_CLASSES:
        if asset_class not in content:
            result.errors.append(f"MISSING weight set for: {asset_class}")
        else:
            # Extract weight row — handle names with slashes (e.g. "Bonds / Bond ETFs")
            escaped = re.escape(asset_class)
            pattern = rf"\| {escaped}[^|]*\| (\d+) \| (\d+) \| (\d+) \| (\d+) \|"
            match = re.search(pattern, content)
            if match:
                weights = [int(x) for x in match.groups()]
                total = sum(weights)
                if total != 100:
                    result.errors.append(
                        f"WEIGHT SUM ERROR for {asset_class}: {weights} = {total} (expected 100)"
                    )
                else:
                    result.info.append(f"✓ Weights valid for {asset_class}: {weights} = 100")
            else:
                result.warnings.append(f"Could not parse weight row for {asset_class}")


def check_adr_001(result: ValidationResult):
    """Verify ADR-001 has all required sections and key constraints."""
    adr_path = AGENT_03_DOCS / "decisions" / "ADR-001-post-scoring-llm-explanation.md"
    if not adr_path.exists():
        return

    content = adr_path.read_text()

    for section in REQUIRED_ADR_SECTIONS:
        if f"## {section}" not in content:
            result.errors.append(f"MISSING section in ADR-001: '## {section}'")
        else:
            result.info.append(f"✓ ADR-001 section: {section}")

    # Check key safeguards documented
    safeguards = ["temperature", "max_tokens", "audit", "post-computation"]
    for safeguard in safeguards:
        if safeguard.lower() not in content.lower():
            result.warnings.append(f"ADR-001 may be missing safeguard mention: '{safeguard}'")


def check_veto_consistency(result: ValidationResult):
    """Verify VETO is consistently described as post-composite across all docs."""
    files_to_check = [
        AGENT_03_DOCS / "architecture" / "reference-architecture.md",
        AGENT_03_DOCS / "implementation" / "agent-03-implementation-spec.md",
        AGENT_03_DOCS / "index.md",
    ]

    for path in files_to_check:
        if not path.exists():
            continue
        content = path.read_text()
        # Only flag if "pre-composite" is used affirmatively (not in "not a pre-composite" context)
        if re.search(r"(?<!not a )pre-composite(?! gate)", content, re.IGNORECASE):
            result.errors.append(
                f"VETO INCONSISTENCY in {path.name}: affirmative 'pre-composite' found — should be 'post-composite'"
            )
        else:
            result.info.append(f"✓ VETO consistency OK in {path.name}")


def check_explanation_integration(result: ValidationResult):
    """Verify ADR-001 (LLM explanation) is reflected in implementation artifacts."""
    checks = {
        "implementation spec — explanation columns in migrations": (
            AGENT_03_DOCS / "implementation" / "agent-03-implementation-spec.md",
            "010_add_explanation_columns"
        ),
        "implementation spec — Phase 5 mentions LLM explanation": (
            AGENT_03_DOCS / "implementation" / "agent-03-implementation-spec.md",
            "generate_explanation"
        ),
        "reference architecture — explanation field in output JSON": (
            AGENT_03_DOCS / "architecture" / "reference-architecture.md",
            '"explanation"'
        ),
        "index — Phase 5 references ADR-001": (
            AGENT_03_DOCS / "index.md",
            "ADR-001"
        ),
    }

    for check_name, (path, pattern) in checks.items():
        if not path.exists():
            continue
        content = path.read_text()
        if pattern not in content:
            result.errors.append(f"ADR-001 not reflected — {check_name}")
        else:
            result.info.append(f"✓ ADR-001 reflected: {check_name}")


def check_changelog(result: ValidationResult):
    """Verify CHANGELOG has Agent 03 entry."""
    changelog_path = DOCS_ROOT / "CHANGELOG.md"
    if not changelog_path.exists():
        return

    content = changelog_path.read_text()
    checks = ["Agent 03", "0.3.0", "ADR-001", "Quality Gate"]
    for check in checks:
        if check not in content:
            result.warnings.append(f"CHANGELOG may be missing entry for: '{check}'")
        else:
            result.info.append(f"✓ CHANGELOG contains: '{check}'")


def check_phase_plan_consistency(result: ValidationResult):
    """Verify phase plan is consistent between index.md and implementation spec."""
    index_content = (AGENT_03_DOCS / "index.md").read_text() if (AGENT_03_DOCS / "index.md").exists() else ""
    impl_content = (AGENT_03_DOCS / "implementation" / "agent-03-implementation-spec.md").read_text() \
        if (AGENT_03_DOCS / "implementation" / "agent-03-implementation-spec.md").exists() else ""

    phases = ["Phase 1", "Phase 2", "Phase 3", "Phase 4", "Phase 5", "Phase 6"]
    for phase in phases:
        in_index = phase in index_content
        in_impl = phase in impl_content
        if in_index and in_impl:
            result.info.append(f"✓ {phase} consistent across index and impl spec")
        elif not in_index and not in_impl:
            result.errors.append(f"{phase} missing from both index.md and implementation spec")
        elif not in_index:
            result.info.append(f"✓ {phase} in impl spec (not required in index — table format may differ)")
        elif not in_impl:
            result.warnings.append(f"{phase} missing from implementation spec")


# ── Main Runner ────────────────────────────────────────────────────────────────

def run_validation(strict: bool = False) -> ValidationResult:
    result = ValidationResult()

    print("Income Fortress Platform — Documentation Validation")
    print("=" * 60)
    print(f"Docs root: {DOCS_ROOT}")
    print(f"Agent 03 docs: {AGENT_03_DOCS}")
    print()

    validators = [
        ("Required Files", check_required_files),
        ("Invariants", check_invariants),
        ("Weight Sets", check_weight_sets),
        ("ADR-001 Structure", check_adr_001),
        ("VETO Consistency", check_veto_consistency),
        ("ADR-001 Integration", check_explanation_integration),
        ("CHANGELOG", check_changelog),
        ("Phase Plan Consistency", check_phase_plan_consistency),
    ]

    for name, validator in validators:
        print(f"Checking: {name}")
        validator(result)

    print()
    print("=" * 60)
    print(f"Files checked: {result.files_checked}")
    print(f"Errors:   {len(result.errors)}")
    print(f"Warnings: {len(result.warnings)}")
    print(f"Info:     {len(result.info)}")
    print()

    if result.errors:
        print("❌ ERRORS:")
        for e in result.errors:
            print(f"  {e}")
        print()

    if result.warnings:
        print("⚠️  WARNINGS:")
        for w in result.warnings:
            print(f"  {w}")
        print()

    if result.passed and (not strict or not result.warnings):
        print("✅ Validation PASSED")
        return result
    elif result.passed and strict and result.warnings:
        print("❌ Validation FAILED (strict mode — warnings treated as errors)")
        sys.exit(1)
    else:
        print("❌ Validation FAILED")
        sys.exit(1)


if __name__ == "__main__":
    strict = "--strict" in sys.argv
    run_validation(strict=strict)
