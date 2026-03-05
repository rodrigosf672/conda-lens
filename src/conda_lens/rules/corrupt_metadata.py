"""
Corrupt Metadata Rule (EDGE-2)

Detects packages with missing or corrupted metadata files that can
cause installation and dependency resolution issues.
"""

import json
from pathlib import Path
from typing import Optional, List, Dict
from conda_lens.rules.base import BaseRule, DiagnosticResult
from conda_lens.env_inspect import EnvInfo


class CorruptMetadataRule(BaseRule):
    """
    Detect packages with missing or corrupted metadata.

    This catches scenarios like:
    - Missing METADATA file in .dist-info
    - Missing REQUIRES.txt or RECORD files
    - Broken or incomplete conda-meta JSON files
    - Wheels built incorrectly with incomplete MANIFEST.in

    Scenario: EDGE-2, EDGE-4 from SCENARIOS.md
    """

    @property
    def name(self) -> str:
        return "corrupt-metadata"

    def check(self, env: EnvInfo) -> Optional[DiagnosticResult]:
        issues: List[Dict[str, str]] = []
        env_path = Path(env.path)

        # Check conda packages metadata
        conda_meta_dir = env_path / "conda-meta"
        if conda_meta_dir.exists():
            issues.extend(self._check_conda_metadata(conda_meta_dir))

        # Check pip packages metadata
        site_packages_candidates = [
            env_path / "lib" / "site-packages",
            env_path / "Lib" / "site-packages",  # Windows
            env_path / "lib" / f"python{env.python_version[:4]}" / "site-packages"
        ]

        for site_packages in site_packages_candidates:
            if site_packages.exists():
                issues.extend(self._check_pip_metadata(site_packages))
                break

        if not issues:
            return None

        message_lines = [f"Found {len(issues)} package(s) with metadata issues:"]
        for issue in issues[:10]:  # Show first 10
            message_lines.append(f"{issue['package']}: {issue['issue']}")

        if len(issues) > 10:
            message_lines.append(f"... and {len(issues) - 10} more")

        return DiagnosticResult(
            rule_name="Corrupt Metadata Check",
            severity="ERROR",
            message="\n".join(message_lines),
            suggestion=(
                "Corrupted metadata can cause import errors and dependency issues. "
                "Try reinstalling the affected packages: "
                "'pip install --force-reinstall <package>' or 'conda install --force-reinstall <package>'"
            )
        )

    def _check_conda_metadata(self, conda_meta_dir: Path) -> List[Dict[str, str]]:
        """Check conda-meta JSON files for completeness."""
        issues = []

        for json_file in conda_meta_dir.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Check for required fields
                required_fields = ['name', 'version']
                missing_fields = [f for f in required_fields if not data.get(f)]

                if missing_fields:
                    issues.append({
                        'package': json_file.stem,
                        'issue': f"Missing fields: {', '.join(missing_fields)}"
                    })

            except json.JSONDecodeError:
                issues.append({
                    'package': json_file.stem,
                    'issue': "Invalid JSON in conda-meta file"
                })
            except Exception as e:
                issues.append({
                    'package': json_file.stem,
                    'issue': f"Cannot read metadata: {str(e)}"
                })

        return issues

    def _check_pip_metadata(self, site_packages: Path) -> List[Dict[str, str]]:
        """Check .dist-info directories for required metadata files."""
        issues = []

        for dist_info in site_packages.glob("*.dist-info"):
            package_name = dist_info.name.replace('.dist-info', '').rsplit('-', 1)[0]

            # Check for METADATA file
            metadata_file = dist_info / "METADATA"
            if not metadata_file.exists():
                issues.append({
                    'package': package_name,
                    'issue': "Missing METADATA file"
                })
                continue

            # Check if METADATA is readable
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if not content or len(content) < 10:
                        issues.append({
                            'package': package_name,
                            'issue': "METADATA file is empty or truncated"
                        })
            except Exception as e:
                issues.append({
                    'package': package_name,
                    'issue': f"Cannot read METADATA: {str(e)}"
                })

            # Check for RECORD file (important for pip operations)
            record_file = dist_info / "RECORD"
            if not record_file.exists():
                issues.append({
                    'package': package_name,
                    'issue': "Missing RECORD file"
                })

        return issues
