# contract-change-v3.1: Superseded outcome

Summary: the v3.1 handoff note that proposed changes to the downstream cue-
authoring consumer is now superseded. The downstream team did not migrate file
readers into the delivery surface; the v3.1 delivery surface described in this
repo is the canonical contract. This archival note records the final outcome.

Key points

- Downstream did not adopt direct reads of analyzer internals; they continued
  to consume the published top-level delivery surface instead.
- The delivery-surface changes were merged here (v3.1): objects for `beats.json`
  / `sections.json`, `field_sources` headers, and the four new top-level files
  (`genre.json`, `drum_events.json`, `loudness.json`, `arrangement_state.json`).
- Because downstream kept using the delivery surface, no further downstream
  migration work was required. The handoff note is therefore archived.

Implications

- The MCP server's delivery surface is the single source of truth for cue-
  authoring inputs. Any signal not promoted to a top-level file during phase 4
  will not reach downstream cue authors.
- The archived handoff note documents the decision and the reasons; it should
  be referenced when considering future delivery-surface changes.

Links and provenance

- Implementation plan: `docs/implementation-plan-v3.3.md`
- Regression guide and checks: `docs/reference/mcp-regression.md`
- Original handoff note (historical): `docs/contract-change-v3.1.md` (this file)

Archival author: MCP team
Date: 2026-09-08
