## Context

The prior arrow proposal modeled the shape as a swept six-point polygon. That abstraction is wrong for the user's target shape. The clarified geometry is much simpler: a four-point polygon symmetric about the line from tail tip to arrow tip.

Using the user's normalized example:

- tail tip `P4 = (0, 0)`
- arrow tip `P0 = (10, 0)`
- upper side point `P2 = (8, 1)`
- lower side point `P3 = (8, -1)`

The final outline is `P4 -> P2 -> P0 -> P3 -> P4`. This produces a long narrow tail from `P4` to the side points and a short head segment from the side points to `P0`.

## Goals / Non-Goals

**Goals:**

- Express `ARROW` as one canonical four-point polygon aligned to the anchor axis.
- Preserve strict symmetry about the tail-tip to arrow-tip axis.
- Keep the head short and wide relative to the long tail by parameterizing side-point position near the arrow tip.
- Reuse the same geometry for chart rendering, preview rendering, body hit testing, and toolbar icon rendering.

**Non-Goals:**

- Do not add new drawing tool types or style variants.
- Do not keep compatibility with the previously proposed six-point silhouette.
- Do not introduce freeform asymmetry or user-editable arrow geometry controls.
- Do not change anchor count, persistence schema, or drawing interaction flow.

## Decisions

### Model the arrow as a four-point symmetric polygon

The polygon will be generated from the two anchors by constructing an axis-aligned local coordinate system and mapping four points:

- tail tip `(0, 0)`
- arrow tip `(L, 0)`
- upper side point `(kL, +w)`
- lower side point `(kL, -w)`

Rationale: this exactly matches the user's clarified topology and keeps the shape definition easy to reason about.

Alternative considered: continue tuning the six-point model. That direction has already proven misleading and should be discarded.

### Keep side points near the arrow tip

The side points should sit near the arrow tip, using a ratio similar to the user's example (`k ~= 0.8`) so the head occupies a minority of the total length.

Rationale: placing the side points near the tip is what makes the shape read as an arrow rather than a centered diamond.

Alternative considered: place side points near the midpoint. That creates a kite or rhombus-like silhouette instead of the intended long-tail arrow.

### Clamp short-arrow dimensions while preserving topology

For short arrows, the implementation should clamp head ratio and half-width so the polygon stays valid, non-degenerate, and symmetric.

Rationale: the topological model must remain stable even when the anchors are close together.

Alternative considered: allow the shape to collapse linearly with length. That risks coincident points and invalid rendering/hit testing.

### Update icon rendering from the same geometry model

The `ARROW` toolbar icon should use the same four-point construction rather than maintaining an approximate or legacy icon shape.

Rationale: the user selects the tool from the icon, so the icon must reflect the actual chart shape.

Alternative considered: leave the icon unchanged. That would preserve an immediate mismatch between the advertised tool and the drawn result.

## Risks / Trade-offs

- [Risk] A mathematically symmetric four-point polygon may still feel visually different from a hand-drawn reference. -> Mitigation: anchor the implementation to the exact topology and relative point placement the user provided.
- [Risk] Very short arrows may push the side points too close to the tips. -> Mitigation: clamp `k` and `w` with minimum spacing from both tail and tip.
- [Risk] The prior six-point change may confuse future implementation work. -> Mitigation: explicitly treat this proposal as the replacement geometry source of truth.

## Migration Plan

1. Replace the current arrow polygon generator with the four-point symmetric model.
2. Update preview rendering, hit testing, and icon rendering to use the same model.
3. Add regression tests for four-point ordering, symmetry, and clamping.
4. No data migration is required; saved `ARROW` drawings continue to render from the new geometry.

## Open Questions

None. The normalized coordinate example from the user is specific enough to serve as the design anchor.
