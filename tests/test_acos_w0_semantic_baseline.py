"""Deterministic regression tests for the documentary ACOS-MIG-W0 baseline."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
BASELINE = "45709e17c58b94d8f95ae2b881ef887d8728584d"

VOCABULARY_PATH = DOCS / "acos-w0-baseline-and-canonical-vocabulary.md"
NAMESPACE_PATH = DOCS / "acos-w0-namespace-registry.md"
TAXONOMY_PATH = DOCS / "acos-w0-historical-import-taxonomy.md"
SEMANTICS_PATH = DOCS / "acos-w0-lifecycle-storage-authority-semantics.md"

CANONICAL_TERMS = {
    "Artifact Type",
    "Producer",
    "Materializer",
    "Runtime Identity",
    "Executor",
    "Reviewer",
    "Decision Authority",
    "Verifier",
    "Signer",
    "Authority",
    "Capability",
    "Grant",
    "Authorization",
    "Evidence",
    "Receipt",
    "State",
    "Lifecycle",
    "NON_CONSUMABLE",
    "LEGACY",
    "IMPORTED",
    "Activation",
    "Operational Entry",
}

IMPORT_CLASSES = {
    "VALID_NATIVE",
    "VALID_LEGACY",
    "REPRODUCED_EVIDENCE",
    "NON_CONSUMABLE",
    "UNTRUSTED_IMPORT",
    "SUPERSEDED",
    "REVOKED",
    "EXPIRED",
    "PROVENANCE_EXCEPTION",
}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def table_keys(text: str, header: str) -> set[str]:
    return set(table_entries(text, header))


def table_entries(text: str, header: str) -> dict[str, str]:
    entries: dict[str, str] = {}
    in_table = False
    for line in text.splitlines():
        if line.startswith(f"| {header} |"):
            in_table = True
            continue
        if not in_table:
            continue
        if line.startswith("|---"):
            continue
        if not line.startswith("|"):
            break
        columns = line.split("|")
        key = columns[1].strip().strip("`")
        value = columns[2].strip() if len(columns) > 2 else ""
        if key:
            if key in entries:
                raise ValueError(f"duplicate table key: {key}")
            entries[key] = value
    return entries


def parse_namespace_registry(text: str) -> dict[str, str]:
    registry: dict[str, str] = {}
    pattern = re.compile(r"^\| `(?P<key>ACOS-[A-Z]+-\*)` \| (?P<meaning>[^|]+) \|$")
    for line in text.splitlines():
        match = pattern.match(line)
        if not match:
            continue
        key = match.group("key")
        meaning = match.group("meaning").strip()
        if key in registry:
            raise ValueError(f"duplicate canonical namespace: {key}")
        if meaning in registry.values():
            raise ValueError(f"conflicting canonical namespace meaning: {meaning}")
        registry[key] = meaning
    return registry


class W0SemanticBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.vocabulary = read(VOCABULARY_PATH)
        cls.namespaces = read(NAMESPACE_PATH)
        cls.taxonomy = read(TAXONOMY_PATH)
        cls.semantics = read(SEMANTICS_PATH)

    def test_baseline_binding(self):
        self.assertIn(BASELINE, self.vocabulary)

    def test_canonical_vocabulary(self):
        self.assertEqual(table_keys(self.vocabulary, "Term"), CANONICAL_TERMS)

    def test_producer_is_attribution_not_authority(self):
        definitions = table_entries(self.vocabulary, "Term")
        producer = definitions["Producer"]
        normalized = " ".join(self.vocabulary.split())
        self.assertIn("logical actor attributable", producer)
        self.assertNotIn("authenticated authority", producer)
        self.assertIn("Producer attribution != governance authority", self.vocabulary)
        self.assertIn("Producer status alone does not confer Authority", normalized)
        self.assertIn("W0 does not establish authenticated runtime identity", normalized)

    def test_reviewer_is_attribution_not_authority(self):
        definitions = table_entries(self.vocabulary, "Term")
        reviewer = definitions["Reviewer"]
        normalized = " ".join(self.vocabulary.split())
        self.assertIn("actor or role attributable", reviewer)
        self.assertNotIn("An authority", reviewer)
        self.assertIn("Reviewer status != governance authority", self.vocabulary)
        self.assertIn("Reviewer status != Decision Authority", self.vocabulary)
        self.assertIn("External Advisory Reviewer", self.vocabulary)
        self.assertIn("non-binding advisory output without possessing governance authority", normalized)
        for authority in (
            "execution authority",
            "state-transition authority",
            "Decision authority",
        ):
            with self.subTest(authority=authority):
                self.assertIn(f"Reviewer status alone does not confer {authority}", normalized)
        self.assertIn("ROLE ATTRIBUTION DOES NOT SELF-CONFER AUTHORITY", self.vocabulary)

    def test_authorization_is_separately_scoped(self):
        definitions = table_entries(self.vocabulary, "Term")
        authorization = definitions["Authorization"]
        normalized = " ".join(self.vocabulary.split())
        self.assertIn("governed permission state or process", authorization)
        self.assertNotIn("A valid decision", authorization)
        self.assertIn("Governance Decision != Authorization", self.vocabulary)
        self.assertIn("Authorization remains scoped to the specific permitted action", normalized)
        self.assertIn(
            "Authorization does not always require a standalone governance Decision artifact",
            normalized,
        )

    def test_required_semantic_inequalities(self):
        required = {
            "Producer != Materializer",
            "Runtime Identity != Provider/Model",
            "Executor != Reviewer",
            "Executor != Decision Authority",
            "Authority != Capability",
            "Capability != Grant",
            "Grant != Authorization",
            "Evidence != Authority",
            "Receipt != Authority",
            "Activation != Operational Entry",
        }
        for statement in required:
            with self.subTest(statement=statement):
                self.assertIn(statement, self.vocabulary)

    def test_namespace_registry_and_lifecycle_families(self):
        registry = parse_namespace_registry(self.namespaces)
        self.assertEqual(
            set(registry),
            {"ACOS-IPS-*", "ACOS-MIG-*", "ACOS-OER-*", "ACOS-OPE-*"},
        )
        for family in (
            "ARTIFACT.*",
            "TASK.*",
            "AUTHORIZATION.*",
            "GIT.*",
            "ACTIVATION.*",
            "OPERATIONAL_ENTRY.*",
        ):
            with self.subTest(family=family):
                self.assertIn(f"`{family}`", self.namespaces)

    def test_namespace_collision_is_rejected(self):
        duplicate = "\n".join(
            (
                "| `ACOS-MIG-*` | Migration Program |",
                "| `ACOS-MIG-*` | Conflicting Program |",
            )
        )
        conflict = "\n".join(
            (
                "| `ACOS-MIG-*` | Shared Meaning |",
                "| `ACOS-OER-*` | Shared Meaning |",
            )
        )
        with self.assertRaises(ValueError):
            parse_namespace_registry(duplicate)
        with self.assertRaises(ValueError):
            parse_namespace_registry(conflict)

    def test_import_taxonomy_is_exact(self):
        self.assertEqual(table_keys(self.taxonomy, "Canonical class"), IMPORT_CLASSES)

    def test_non_consumable_never_confers_authority(self):
        required = (
            "authorization input",
            "execution authority",
            "state-transition authority",
            "Decision authority",
        )
        non_consumable_row = next(
            line for line in self.taxonomy.splitlines() if line.startswith("| `NON_CONSUMABLE`")
        )
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, non_consumable_row)

    def test_historical_preservation_prohibitions(self):
        for phrase in (
            "retroactive signing",
            "retroactive authentication",
            "silent authority upgrade",
            "provenance rewriting",
            "historical byte rewriting",
            "deletion-based repair",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.taxonomy)

    def test_evidence_does_not_upgrade_authority(self):
        for statement in (
            "Git history != governance authority",
            "Audit evidence != authorization",
            "Schema validity != authenticated authority",
            "Linter PASS != authenticated authority",
            "Declared PRODUCER != authenticated Producer",
            "Persistence Receipt != Decision Authority",
        ):
            with self.subTest(statement=statement):
                self.assertIn(statement, self.semantics)

    def test_managed_conversation_boundary(self):
        normalized = " ".join(self.semantics.split())
        self.assertIn("MANAGED_CONVERSATION", self.semantics)
        self.assertIn("TARGET GOVERNANCE SEMANTIC /", self.semantics)
        self.assertIn(
            "NOT CURRENTLY OPERATIONALLY SUFFICIENT FOR CANONICAL TASK_MATERIALIZED SEMANTICS",
            normalized,
        )
        self.assertIn("Storage, reference, or digest uncertainty must `FAIL CLOSED`", self.semantics)

    def test_current_storage_source_tension_is_preserved(self):
        normalized = " ".join(self.semantics.split())
        self.assertIn("docs/task-state-machine.md", self.semantics)
        self.assertIn("canonical task-readiness path", normalized)
        self.assertIn("CODEX_WORKFLOW.md", self.semantics)
        self.assertIn("TASK FILE REQUIRED:NO", self.semantics)
        self.assertIn("Current sources are not fully harmonized", self.semantics)
        self.assertIn(
            "W0 DOES NOT RETROACTIVELY RESOLVE THIS CURRENT-SOURCE TENSION BY REINTERPRETATION",
            normalized,
        )
        self.assertIn("It does not silently amend", self.semantics)
        self.assertNotIn(
            "repository materialization remains the current operational rule",
            self.semantics,
        )

    def test_w1_and_w2_deferrals(self):
        normalized = " ".join(self.semantics.split())
        self.assertIn("Current Contract, schema, and linter files remain unchanged", normalized)
        self.assertIn("belongs to W1", normalized)
        self.assertIn("runtime identity", normalized)
        self.assertIn("persistence runtime belong to W2", normalized)
        self.assertIn("No runtime, writer, grant, receipt service", normalized)


if __name__ == "__main__":
    unittest.main()
