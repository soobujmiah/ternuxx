# GitHub Actions immutable pin review — 2026-10-24

Evidence class: read-only review of upstream GitHub releases, tags and action manifests, followed by a repository workflow update.

## Verified refs

| Action | Release | Immutable commit SHA | Manifest runtime |
|---|---|---|---|
| `actions/checkout` | [v7.0.1](https://github.com/actions/checkout/releases/tag/v7.0.1) | `3d3c42e5aac5ba805825da76410c181273ba90b1` | `node24` |
| `actions/setup-python` | [v7.1.0](https://github.com/actions/setup-python/releases/tag/v7.1.0) | `6d4fd22b20465ccc0f7354476588e8df7c9ca0e0` | `node24` |

The commits were resolved from each upstream release tag and each `action.yml` at that exact commit was inspected. These repositories report the above versions as latest releases on 2026-10-24. The Ternuxx workflows run on GitHub-hosted `ubuntu-latest`; no self-hosted runner compatibility claim is made.

## Change and verification

All six workflow references in `.github/workflows/repo-contract.yml` and `.github/workflows/repo-knowledge-sync.yml` now use the reviewed full commit SHAs, with release-version comments. Workflow permissions, triggers, job ordering, and state-sync behavior were not changed.

The repository adds a regression test that checks all six action references against the reviewed SHA/version pairs. It passed locally, and both workflow YAML files parsed with 1 and 2 jobs respectively. The [GitHub Actions run 40104475043](https://github.com/soobujmiah/ternuxx/actions/runs/40104475043) on commit `0e1675005dc48fb1be2ceb552678f6b303a66d80` completed successfully: checkout and setup-python ran at the pinned SHAs, the full repository test step passed, and the repository-state sync job completed. This verifies the pin migration on GitHub-hosted `ubuntu-latest` for this run.
