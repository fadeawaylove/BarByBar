## Context

The codebase already treats `DrawingToolType.ARROW` as a dedicated filled-polygon drawing. The existing implementation computes a symmetric eight-point shape in `ChartWidget._drawing_arrow_polygon()` and reuses a similar geometry in the toolbar icon painter. The user's reference image makes it clear that this shape is not merely "wider"; it uses a different silhouette:

- a single sharp tail point
- long wedge-like body edges instead of a narrow shaft
- one major shoulder expansion near the head
- a short, heavy head rather than a long standard triangle

The change should preserve the current tool identity and interaction model. Users should still select the same `ARROW` tool and place it with two anchors. The work is visual and geometric, not behavioral.

## Goals / Non-Goals

**Goals:**

- Make the existing `ARROW` drawing visually match a six-point swept wedge closer to the supplied reference.
- Use one canonical polygon generator for persisted rendering, hover feedback, preview rendering, and hit testing.
- Keep the tool's persistence, anchors-required count, and selection/editing behavior unchanged.
- Keep the arrow icon recognizable and aligned with the in-chart shape.

**Non-Goals:**

- Do not add a new drawing tool type, style toggle, or alternate arrow families in this change.
- Do not change drawing serialization format unless a small internal style default is required.
- Do not alter drawing interactions such as anchor placement count, dragging semantics, or property dialog behavior.
- Do not attempt freeform hand-drawn asymmetry; the result should be deterministic from the two anchors.

## Decisions

### Use a six-point swept-arrow template

Replace the current regular polygon with a six-point polygon that follows this ordered silhouette: tail tip, upper shoulder, upper head base, arrow tip, lower head base, lower return edge.

Rationale: this is the closest deterministic geometry to the reference image while staying simple enough to reason about, test, and reuse in both chart rendering and icon rendering.

Alternative considered: keep the current polygon and only tune width ratios. That would still preserve a regular symmetric arrow body and would not create the long-wedge silhouette seen in the reference.

### Keep the shape deterministic and anchor-driven

Compute the polygon entirely from the two anchors and normalized proportional constants derived from arrow length.

Rationale: deterministic geometry keeps save/load, preview, and hit testing aligned and avoids introducing state that must be persisted or exposed in the properties dialog.

Alternative considered: store arrow-specific style parameters such as shoulder position or head width. That adds unnecessary complexity for a single reference-driven shape update.

### Share one geometry model between chart and icon rendering

The toolbar icon should either call the same helper or mirror the same point-template math so the icon advertises the actual drawing shape.

Rationale: the current mismatch risk is high whenever icon geometry and chart geometry drift apart. This change is mainly visual, so consistency matters.

Alternative considered: update only the chart rendering and leave the icon approximate. That would make the UI preview misleading.

### Preserve hover and hit testing by reusing the final polygon

Hover detection and any body hit testing should continue to use the final polygon path/bounds instead of a separate simplified line model.

Rationale: once the arrow body becomes a wedge rather than a regular shaft, line-based assumptions are less reliable. Using the final polygon avoids "looks clickable here, but isn't" mismatches.

Alternative considered: keep separate simplified hit geometry. That reduces implementation work but increases visual/interaction drift.

## Risks / Trade-offs

- [Risk] The reference arrows have slight visual irregularities that a deterministic polygon cannot reproduce exactly. -> Mitigation: match the dominant silhouette traits: sharp tail, long wedge body, pronounced shoulder, short heavy head.
- [Risk] Very short arrows may collapse into awkward geometry when proportional dimensions compete. -> Mitigation: clamp head length, shoulder width, and return-edge spacing with tested minimums.
- [Risk] Changing the polygon may make existing saved arrows look noticeably different after reload. -> Mitigation: this change intentionally redefines the visual contract of `ARROW`; add tests and note that persistence format remains stable while rendering is upgraded.
- [Risk] Duplicating chart math and icon math may drift over time. -> Mitigation: centralize the geometry helper or keep a clearly mirrored calculation with regression tests.

## Migration Plan

1. Update the canonical arrow polygon generator to the new six-point swept shape.
2. Update arrow preview/body rendering and hit testing to consume the new polygon without changing tool metadata.
3. Update the arrow toolbar icon to reflect the new silhouette.
4. Add regression tests for geometry shape, short-arrow clamping, and icon/render consistency.
5. No data migration is required; existing saved `ARROW` drawings reuse the new geometry when rendered.

## Open Questions

None. The implementation should follow the long-wedge six-point silhouette as the closest match to the user's reference.
