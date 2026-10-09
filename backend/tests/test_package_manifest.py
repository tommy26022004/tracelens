"""End-to-end contract tests for realistic package specifications."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.ingestion.package_manifest import (
    RealisticPackageManifest,
    default_realistic_package_manifest,
)


def test_default_manifest_round_trips_and_meets_workload() -> None:
    manifest = default_realistic_package_manifest()
    restored = RealisticPackageManifest.model_validate_json(manifest.model_dump_json())

    assert restored == manifest
    assert restored.expected_file_count == 32
    assert restored.expected_page_count == 337
    assert len(restored.account_ids) == 2
    assert restored.financial_years == [2023, 2024, 2025]


def test_manifest_rejects_workload_below_acceptance_threshold() -> None:
    manifest = default_realistic_package_manifest().model_dump()
    manifest["document_specs"] = manifest["document_specs"][:1]

    with pytest.raises(ValidationError, match="outside acceptance range"):
        RealisticPackageManifest.model_validate(manifest)
