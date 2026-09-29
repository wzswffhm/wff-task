# Proposal 交付格式预检

`scripts/validate_proposals.py` validates proposal package names, package structure,
strict JSON shape, benchmark task membership, and benchmark domain prefixes.
It uses only the Python standard library and the checked-in
`references/benchmark_tasks.json`; validation never accesses the network or
the benchmark source directories.

## Usage

Run these commands from the Skill root. Validate one package:

```bash
python3 scripts/validate_proposals.py \
  /absolute/path/to/terminal_bench3_bps-phase-vectorized
```

Validate every immediate package directory in a collection:

```bash
python3 scripts/validate_proposals.py \
  /absolute/path/to/proposal-batch
```

Add `--json` for a machine-readable report. Exit status is `0` when every
package passes, `1` for proposal validation failures, and `2` when the bundled
mapping cannot be loaded.

## Enforced rules

- A package is named `<benchmark>_<proposal_name>` and contains exactly
  `proposal.json` and the `sources/` directory.
- An empty `sources/` directory may omit `README.md`. A non-empty `sources/`
  directory must contain `sources/README.md` as a regular file.
- Benchmark values are the exact spellings from `expected_form.json`,
  including the existing `froniterSWE` spelling.
- `proposal.json` is strict UTF-8 JSON. Duplicate keys, missing keys, extra
  keys, wrong types, empty text, and an empty difficulty list are rejected.
- `domain` has two or three non-empty `/`-separated levels.
- Terminal Bench 3 and 4 domains start with the task's exact
  `metadata.category/metadata.subcategory`. An optional third level is allowed.
- Benchmarks with only `metadata.category` use
  `<benchmark>/<metadata.category>` as the required prefix. This applies to
  `deepSWE`, `swe_marathon`, and `froniterSWE`; an optional third level is
  allowed.
- ProgramBench's official `task.yaml` files have `language` and sometimes
  `difficulty`, but no category or domain. Its `related_question` is checked
  against the official 200 task directory names, while its domain is only
  subject to the common two-to-three-level format rule.
- `related_question` must exactly match a task directory in the selected
  benchmark.
- Proposal type `B` requires `proposal_sources` to contain a plausible Git
  repository URL. Types `A` and `C` do not.

## Offline mapping

`references/benchmark_tasks.json` currently contains 507 tasks:

| Benchmark | Tasks | Domain metadata |
| --- | ---: | --- |
| `terminal_bench3` | 74 | category + subcategory |
| `terminal_bench4` | 66 | category + subcategory |
| `programbench` | 200 | no official domain |
| `swe_marathon` | 20 | category |
| `deepSWE` | 113 | category |
| `froniterSWE` | 34 | category |

Each benchmark entry records the source revision used to generate the mapping.
The mapping is part of the Skill package. Updating it is a maintainer action:
regenerate or replace the complete file, retain `schema_version=1`, update each
source revision and task count, then rerun the validator tests and regenerate
the Skill manifest.
