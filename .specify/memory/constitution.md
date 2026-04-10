<!-- Sync Impact Report
Version change: 1.1.0 → 1.2.0
Changed: Principle I (removed fieldupload from current module list; noted as future)
Changed: Principle VIII (clarified installer bundles rnx2rtkp; dev from source is separate)
Templates updated: ✅ constitution.md
-->

# AVGeoSys - PPK Tool Constitution

## Core Principles

### I. Single Responsibility per Module
Each module (ppk, interpolator, exif, report, events, geoid) MUST have one
clearly defined responsibility. No module may perform operations outside its domain.
Cross-cutting concerns (logging, config) belong in dedicated support modules.
Utility modules planned for future specs (e.g., fieldupload) follow the same rule
when implemented.

### II. Dual Interface (CLI + GUI) — Non-Negotiable
Every core capability MUST be accessible from both the Tkinter GUI and the CLI (argparse).
The GUI is the primary user-facing interface; the CLI enables automation and scripting.
Core logic MUST NOT depend on either interface — it belongs exclusively in `avgeosys/core/`.

### III. Test-First for Core Logic
TDD is mandatory for `avgeosys/core/` modules — especially any code involving
math, file parsing, or data transformation (interpolation, DMS conversion, MRK/POS
parsing). Tests MUST be written before implementation for these modules.
The GUI (`avgeosys/ui/`) is validated by manual execution, not unit tests.
Unit tests for each core module; integration test for the full PPK → Geotag pipeline.
Test data (sample .MRK, .pos files) MUST exist in `tests/data/`.

### IV. External Tool Isolation
RTKLIB (`rnx2rtkp.exe`) is the only permitted external binary dependency.
Its path MUST be configured in `avgeosys/config.py` only — never hardcoded elsewhere.
All subprocess calls to external tools MUST be wrapped in the `core/ppk.py` module.
On Windows, subprocess windows MUST be hidden (`CREATE_NO_WINDOW`).

### V. Graceful Degradation
Optional features (geoid height via pyproj) MUST fall back gracefully when the
dependency is unavailable. The fallback MUST be documented and produce a warning log.
The tool MUST remain functional for the core PPK → EXIF workflow even without
optional dependencies.

### VI. Simplicity and Minimal Dependencies
Core pipeline: piexif, simplekml, pandas, numpy, pyproj (optional).
No web frameworks, databases, or heavy ORMs permitted.
New dependencies require explicit justification and must be added to `setup.py`.

### VII. Cross-Platform Support
Code MUST run on Windows (primary) and Linux.
Platform-specific code (Windows `CREATE_NO_WINDOW`, `.exe` binaries) MUST be
guarded with `sys.platform` checks or `platform.system()`.

### VIII. Standalone Distribution
The tool MUST be distributable as a standalone Windows `.exe` (no Python install
required) via PyInstaller. The Inno Setup script (`AVGeoSys.iss`) MUST be
maintained alongside the source. Packaging MUST be verified as part of each
release — a release that cannot be packaged is not a release.
The installer MUST bundle `rnx2rtkp.exe`, `ppk_rnx2rtkp.conf`, and
`glonass_biases.txt` so end users (surveyors) need not install RTKLIB separately.
When running from source (development), the developer is responsible for providing
`rnx2rtkp.exe` and setting its path in `config.py`.

## Quality Standards

- All new code MUST pass flake8 (PEP8) linting with no errors.
- mypy type checking MUST pass with no errors on core modules.
- pytest coverage MUST cover all core functions (unit) and the full pipeline (integration).
- CI/CD via GitHub Actions MUST test Python 3.8–3.11 on Ubuntu and Windows.

## Development Workflow

1. For `core/` changes: write failing tests first, then implement until tests pass.
2. For `ui/` changes: implement, then validate by running the GUI manually.
3. Lint (flake8) and type-check (mypy) before committing.
4. Update README if user-facing behavior changes.
5. Commit with descriptive message referencing the module changed.
6. Before a release: verify PyInstaller packaging produces a working `.exe`.

## Release Checklist

Every release MUST update ALL of the following before tagging:

| File | Branch | What to change |
|------|--------|----------------|
| `avgeosys/__init__.py` | `master` | `__version__` |
| `AVGeoSys.iss` | `master` | `AppVersion` |
| `version.json` | `master` **and** `main` | version + url + notes |

**The `version.json` on `main` is the live update feed** — `updater.py` fetches from
`https://raw.githubusercontent.com/joaomsas/avgeosys-ppk-exif-tool/main/version.json`.
Committing only to `master` leaves the auto-update silent: installed users will not
see the new version until `main` is updated.

Workflow to push `version.json` to `main` without merging all of `master`:
```
git checkout origin/main -b tmp-release
git checkout master -- version.json
git commit -m "chore: bump version.json to vX.Y.Z on main"
git push origin tmp-release:main
git checkout master && git branch -d tmp-release
```

## Governance

This Constitution supersedes all other development practices.
Amendments require: documentation of the change, rationale, and migration plan.
All code reviews MUST verify compliance with Principles I–VIII.
Complexity MUST be justified — prefer the simplest implementation that satisfies requirements.
Use `README.md` for runtime development guidance.

**Version**: 1.2.0 | **Ratified**: 2026-04-01 | **Last Amended**: 2026-04-01
