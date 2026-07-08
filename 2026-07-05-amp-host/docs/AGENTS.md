# Documentation instructions

## Scope

This directory contains design and implementation notes for Amp Host. Treat these files as living design docs, not generated artifacts.

## Conventions

- Keep docs consistent with the current implementation in `amp_host/`.
- When changing launch behavior, update the command examples in `README.md`, `docs/herdr-integration-design.md`, and `docs/herdr-implementation-plan.md`.
- Preserve useful validation evidence, but do not add stale command output or machine-specific absolute paths.
- Prefer concise dated decisions over long speculative sections when documenting new behavior.

## Safety

- Do not document private tokens, tailnet names, account identifiers, or local-only credentials.
- Do not imply `amp-host.config.json` should be committed; only the example config belongs in the repo.
- Keep Herdr and Amp examples scoped to safe commands that create, inspect, or close test panes.

## Verification

After documentation-only edits, run:

```bash
rg "amp --mode deep|--workspace|remote" README.md docs
```

For docs that describe code behavior, also run the narrow relevant code check:

```bash
uv run python -m compileall amp_host
```
