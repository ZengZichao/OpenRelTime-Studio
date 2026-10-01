# Changelog

**Language: English** · [简体中文](CHANGELOG-zh.md)

All notable changes to **OpenRelTime Studio** are documented here. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), the versioning
follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

- Repository maintenance scaffolding: a security policy (`SECURITY.md`),
  contribution guide (`CONTRIBUTING.md`), `CODEOWNERS`, issue and
  pull-request templates, and a tag-triggered release workflow
  (`.github/workflows/release.yml`) that builds the sdist/wheel and the
  frozen macOS `.app` bundle and attaches them to the release named after
  the tag.
- CI now type-checks with mypy, reports test coverage, caches pip downloads
  and reads the engine pin from a single `ENGINE_REF` variable shared in
  spirit with the release workflow (see the release checklist in
  `CONTRIBUTING.md`).

### Changed

- Repository settings: squash-only merges onto `main`, automatic deletion of
  merged head branches, and required status checks protecting `main`.

## 0.1.0 — 2026-09-29

OpenRelTime Studio is a native desktop application (PySide6, no browser
involved) for relative-rate molecular dating. It needs no terminal and carries
no algorithm of its own: every figure on screen is produced by the installed
`openreltime` distribution through its public Python API, called from the single
adapter layer `openreltime_studio/adapters/openreltime_adapter.py`, so a
session done in the GUI reproduces exactly on the command line. Requires
Python ≥ 3.10; distributed under GPL-3.0-or-later.

### Added

- **Tree input.** Newick and NEXUS timetrees, read in the background from
  **File ▸ Open tree file…** (`Ctrl+O`) or from the **Tree file** row of the
  **Import** group. The Import group also holds the reading settings that the
  engine consumes: outgroup (comma-separated, optional), file format
  (`newick` / `nexus`), polytomy handling (`error` / `random`) and outgroup
  check (`error` / `warn`); the format is detected from the extension and can be
  overridden by hand.

- **RRF dating.** Relative evolutionary rates and relative divergence times on
  the **RRF** tab, with the geometric or arithmetic mean, optional
  normalisation, and the rate-ratio guard (threshold 20, switchable off).

- **Interactive calibration.** Calibration points are placed by clicking an
  internal node on the tree and typing a lower and/or upper bound in Mya, with
  an optional density (`uniform`, `exponential`, `normal`, `lognormal`) and its
  `key=value;…` parameters; a point targeting a `taxon_set` is resolved to that
  clade's MRCA, and re-clicking a node replaces its point. Points can also be
  loaded from a TSV file. Absolute times come from the **Calibration** tab with
  either the `bounds` method or the replicated `effective` method (draw count
  2–100 000, default 10 000, with an optional fixed seed).

- **Confidence intervals.** Node-age intervals on the **CI** tab, plotted as
  error bars, at a confidence level of 0.95 (default), 0.90 or 0.99, with
  optional per-branch variances supplied as a TSV file and an optional site count
  (default 1 000); without a site count the interval carries only the
  rate-heterogeneity component and the tab says so.

- **CorrTest.** Rate autocorrelation across the tree — CorrScore, P-value band,
  ρ_s and ρ_ad with their decay — with sister-pair resampling, an optional fixed
  seed, and an optional anchor node and time.

- **ddBD.** The density-dependent birth–death diversification prior, measured by
  `SSE` or `KL`, with an optional anchor, drawn as a node-time histogram with the
  fitted density on the canvas.

- **Background workers, progress and cancellation.** Every stage above runs in a
  `QThread` (`openreltime_studio/workers/analysis_workers.py`), so the window
  stays responsive; calibration reports progress and can be cancelled, and a
  cancelled result is discarded rather than applied. Engine warnings are
  collected from the `openreltime` logger and shown in an in-window panel with a
  count badge.

- **Orientable rectangular tree canvas.** A time-scaled rectangular tree with
  branches coloured by rate, calibration markers and CI error bars, redrawn
  under **View ▸ Root position** with the root on the left (default), right, top
  or bottom — the time axis flips while the tick values stay true, tip labels
  stay on the tip side, and the current view is re-rendered without re-analysis.

- **Results view.** A read-only **Node table** of per-node results with
  translated headers, a summary line carrying the headline numbers of the last
  finished analysis (including the CorrTest and ddBD results), and a status bar
  that reports what happened and what is running.

- **Export.** **File ▸ Export results…** (`Ctrl+E`) writes into a chosen
  directory: the engine's result set under the fixed prefix `openreltime_result`
  (CSV tables, the NEXUS tree where one applies, and the JSON report, which for
  a calibration also records the tree path, calibration file, outgroup and
  reading settings), a 200 dpi PNG of whatever the canvas currently holds
  (`timetree.png`, `ci.png`, `corrtest.png` or `ddbd.png`), `calibrations.tsv`
  when the exported pipeline contains a calibration or CI step, and an
  executable `run_reltime.sh`.

- **Equivalent command line.** A panel that mirrors every step as the exact
  `openreltime` command, in pipeline order, with `--fmt`, `--resolve`,
  `--outgroup-check` and an absolute `-i` path spelled out; one click copies it,
  and the exported script replays the session on a cluster.

- **Bundled example.** **File ▸ Open Bundled Example…** (`Ctrl+I`) loads a
  24-taxon marsupial/monotreme time tree and three demo calibration points from
  inside the package (`openreltime_studio/examples/`), so the whole
  RRF → calibration → CI → CorrTest → ddBD → export workflow can be walked
  without any data of your own; the calibration bounds are illustrative
  placeholders, not published dates.

- **Full English / Chinese localisation.** Every menu, label, tooltip,
  placeholder, table header, status message, progress dialog and message box is
  resolved from per-namespace JSON catalogs (`locales/en`, `locales/zh`) and
  switches live under **View ▸ Language**, re-rendering dynamic text and
  repainting the canvas — no restart, no re-analysis.

- **Light and dark themes.** All colours are design tokens in `themes.py`
  (`LIGHT` / `DARK`), consumed by one shared stylesheet template and a matching
  `QPalette`; the canvas re-reads its colours at draw time, so branch colouring,
  calibration markers, CI error bars and the ddBD density plot stay legible in
  dark mode. Switched live under **View ▸ Theme**.

- **Remembered preferences.** Language, theme and root position, the last tree,
  calibration and export directories, and the window geometry are stored under
  `QSettings("OpenRelTime", "Studio")` and restored at start-up; the first
  launch is English + Light + root on left.

- **Vector application icon.** `resources/icons/OpenRelTime-Studio.svg` is the
  single source of truth, rasterised by `appicon.py` into a multi-size `QIcon`
  (16–512 px) through `QtSvg` with a `QPainter` fallback; a simplified
  `OpenRelTime-Studio-symbolic.svg` is selected automatically at 64 px and
  below, and `resources/make_icon.py` regenerates `icon.png` / `icon.icns`.

- **Quitting safety.** Closing the window while jobs are running asks first,
  with **No** as the default answer.

- **Translation gate.** `tools/check_i18n.py` and
  `openreltime_studio/tests/test_i18n_catalogs.py` fail the build on hard-coded
  Chinese UI literals, hard-coded colours outside `themes.py`, keys missing from
  either language, mismatched `{placeholders}`, and dead catalog entries.

- **Documentation.** A paired English / Chinese user guide
  ([usage-en.md](docs/usage-en.md) ·
  [usage-zh.md](docs/usage-zh.md)), this changelog, and
  [`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md), each with its Chinese
  counterpart.

- **Packaging.** `openreltime-studio --self-check`, a windowless check that the
  catalogs, the bundled example files and both icon variants all resolve inside
  the installed package; and the PyInstaller spec
  `openreltime_studio/resources/OpenRelTimeStudio.spec`, which bundles the
  bilingual catalogs, the icons and the example, forces `console=False` and sets
  the bundle identifier `org.openreltime.studio` to build a double-clickable
  macOS application.

- **Test suite.** Adapter, catalog, regression, localization, tree-orientation,
  bundled-example and docs-hygiene suites, runnable headless with
  `QT_QPA_PLATFORM=offscreen python -m pytest`, plus
  `openreltime_studio/tests/smoke_gui.py`, which drives the real window off
  screen through every stage.
