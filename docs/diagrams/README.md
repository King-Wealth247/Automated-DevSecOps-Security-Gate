# Diagrams

Diagrams use [Mermaid](https://mermaid.js.org/), which GitHub renders natively in
Markdown — open these files on GitHub (not as raw text) to see them, or preview them in
an editor with Mermaid support.

| File | Shows |
|---|---|
| [`pipeline-dag.md`](./pipeline-dag.md) | The actual `.github/workflows/ci.yml` job graph — every job, its dependencies, and why `publish`/`deploy-flyio-temp`'s conditions are more than a plain `if:` |
| [`decision-flow.md`](./decision-flow.md) | How the three scanners' reports become one PASS/BLOCK decision, and why that decision is fail-closed |

Diagrams describe the pipeline as of 2026-09-29 (the first fully-green end-to-end run,
`36593239493`). If `ci.yml`'s job graph changes, update `pipeline-dag.md` to match —
these are meant to track the real file, not a snapshot frozen at write time.
