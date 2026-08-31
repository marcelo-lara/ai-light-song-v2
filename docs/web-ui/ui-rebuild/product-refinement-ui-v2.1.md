# Product Refinement — Web UI v2.1

Active worklist for a **polish and fix pass** on the shipped UI v2 rebuild of the
internal artifact debugger in `ui/`. Items here are scoped and ready to be turned
into an implementation plan.

## Version convention

`UI v2.1` is a point release of the **debugger web app** on top of the `UI v2`
rebuild — no new architecture, no analyzer-contract changes. It collects defects
and small refinements found during the D3 live-browser parity pass on `UI v2`.

| Carrier | Rule |
| --- | --- |
| App release | `UI v2.1`. Tagged `ui-v2.1` in git on completion. |
| Refinement doc | this file. |
| Implementation plan | `implementation-plan-ui-v2.1.md`, archived when the pass ships. |
| Story specs | the Epic 8 story files in `docs/web-ui/8.*.md` are updated in the item that changes their behaviour. |

## Release goal

Close the visual and interaction gaps found running `UI v2` in a real browser
against real songs, so the `ui-v2` parity gate can be signed off and the app is
comfortable to operate day to day.

Scope is confined to `ui/`. Read-only against `data/analysis/**` except the two
existing human-save paths. No analyzer artifact, `schema_version`, or
`build_ui_data` contract changes.

---

## 1. Collapsed lane shows the title only

**Intent.** A collapsed lane currently still renders a second line beneath the
title (the sub-caption / "collapsed" legend). In a stack of collapsed lanes that
second line is noise and makes each collapsed row taller than it needs to be.

**Change.** When a lane is collapsed, render only the lane title in the label
column. Drop the second text line for the collapsed state; it returns when the
lane is expanded. The faint mini data-strip summary in the collapsed row is
unchanged and still renders.

**Acceptance.** Collapsing a lane leaves a single-line label with its data strip
intact; expanding it restores the sub-caption.

## 2. Left panel collapsed by default

**Intent.** The left panel (lane list / navigation) opens by default and takes
horizontal space away from the timeline on every load.

**Change.** The left panel starts collapsed. It opens only when the burger
(hamburger) control is clicked, and closes again the same way.

**Acceptance.** A fresh load shows the timeline at full width with the left panel
closed; clicking the burger toggles it.

## 3. "Fit to width" is an icon-only control

**Intent.** The fit-to-width button carries a text label and a border, which is
heavier than the rest of the footer controls.

**Change.** Render fit-to-width as an icon only — no text label, no border. On
hover, change its background colour (matching the other icon controls' hover
treatment).

**Acceptance.** The control is a single icon with no border; hovering changes its
background; its action is unchanged.

## 4. "Hide all" button on the lane list

**Intent.** There is no fast way to clear the timeline down to nothing; each lane
has to be hidden individually.

**Change.** Add a "hide all" button to `tl-lanelist` that sets every lane to
hidden in one action. (Pairs with the existing per-lane show/hide.)

**Acceptance.** Clicking "hide all" hides every lane; lanes can then be shown
again individually from the list.

## 5. Collapse/expand control keeps a fixed position

**Intent.** The lane collapse/expand caret currently sits so that its position
shifts between the collapsed and expanded states, so the click target moves out
from under the pointer after each toggle.

**Change.** Anchor the collapse/expand icon at the top of the lane label,
immediately next to the title, in the same place for both states. Toggling a lane
must not move the icon, so it can be clicked repeatedly without repositioning the
pointer.

**Acceptance.** The caret stays at a fixed point beside the title through repeated
collapse/expand toggles.

---

## Bugs — Open

**B1. Waveform lane renders nothing on a real song.**
On a song with a real audio file loaded, the Waveform Anchor lane is blank — no
waveform is drawn. (Observed on a song whose segments are "Ambient Opening" /
"Vocal Spotlight", i.e. not the `_test_song` fixture, so this is distinct from
the known `_test_song`-has-no-mp3 fallback in `docs/web-ui/ui-issues.md`
finding 2.) Needs a scoped fix decision — wavesurfer load/render path vs. the
shell's own draw over it.

**B2. FFT Bands, RMS Loudness, and Loudness Envelope only cover part of the
timeline.**
These three continuous lanes render their data only across the opening span of
the timeline rather than the full song duration. They should be drawn across the
entire timeline width. Needs a decision on whether this is a rendering-extent
bug (canvas width / x-mapping) or a data-window limit, and what the intended
full-timeline behaviour is.

## Out of scope for UI v2.1

- Any analyzer-artifact, `schema_version`, or `build_ui_data` contract change.
- New lanes or new panel modes beyond the `UI v2` set.
- Rebuilding the `validation` (Regression Overlay) stub into a full lane.
