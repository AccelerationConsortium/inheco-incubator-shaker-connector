# Contributing

Start with the simulator; physical hardware is not required for the test suite.

```sh
uv sync --python 3.12 --extra test --extra dev --locked
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run pytest -q
uv build
```

Keep the SiLA feature layer separate from device operations and wire transport.
Changes to device behavior should identify the manufacturer command and units,
include a regression test, and describe the completion/readback semantics.
Never turn an acknowledged command into an unsupported claim of physical completion.

For hardware reports, include OS, Python version, device model, firmware, floor
mapping, expected behavior and a minimal reproduction. Remove credentials and
identifying information from logs before attaching them. Distinguish simulated,
pseudo-terminal and actual hardware results.

The default mode remains simulation. Startup must not initialize, move, calibrate,
clear faults or replay previous device actions. Do not blindly retry writes after
an ambiguous timeout. Keep READMEs, API semantics and VALIDATION.md consistent.

The Chinese tutorial's source is `docs/TUTORIAL.zh-CN.md`. Regenerate its standalone
HTML after edits with `uv run python scripts/render_tutorial.py`.
