## Context

`ChartWidget` already tracks enough semantic state to provide precise cursor feedback:

- `InteractionMode` distinguishes browse, drawing, and order-preview modes.
- `HoverTargetType` distinguishes anchors, drawing bodies, order lines, and trade links.
- `DrawingDragMode` distinguishes anchor dragging from whole-body translation.

Despite that, `_sync_cursor()` still maps several different states to the same cursor. In particular, drawing anchors, drawing bodies, and trade links are grouped too aggressively, and dragging a control point is not clearly separated from dragging the whole drawing.

## Goals / Non-Goals

**Goals:**

- Make cursor feedback communicate the current editing intent more clearly.
- Differentiate anchor hover from drawing-body hover.
- Differentiate anchor dragging from whole-drawing dragging.
- Provide directional cursor hints for constrained drawing edits where practical.
- Preserve the existing drawing behavior and editing model.

**Non-Goals:**

- Do not change how drawings are selected, moved, or persisted.
- Do not redesign hit testing or anchor geometry.
- Do not introduce custom bitmap cursors in this change.
- Do not alter order-preview cursor behavior except where it intersects with drawing-state precedence.

## Decisions

### Prioritize interaction semantics over object type

Cursor mapping should be driven by user intent:

- placing a new drawing
- hovering an editable anchor
- dragging an anchor
- hovering a movable drawing body
- dragging the drawing body

Rationale: users understand "what this action will do" faster than "what object type is under the pointer".

Alternative considered: keep mapping mostly by `HoverTargetType`. That preserves current ambiguity between anchor editing and whole-body movement.

### Use `PointingHand` for editable anchors and hand cursors for whole-body move

Editable drawing anchors should use `PointingHandCursor` on hover. Movable drawing bodies should use `OpenHandCursor` on hover and `ClosedHandCursor` while being dragged.

Rationale: this is a low-risk improvement that sharply separates "edit a point" from "grab the object".

Alternative considered: use `OpenHandCursor` for both anchors and bodies. That is the current problem and does not communicate edit intent.

### Use directional resize cursors for constrained dragging where the axis is obvious

For horizontal-only or vertical-only editing interactions, the cursor should switch to `SizeVerCursor` or `SizeHorCursor` as appropriate. Free anchors can continue to use `CrossCursor` while dragging.

Rationale: constrained motion should be visible before and during the drag.

Alternative considered: keep all anchor drags on `CrossCursor`. That is simpler but wastes the semantic information the widget already has.

### Keep placement mode simple and consistent

When the user is actively placing a drawing, the cursor should remain `CrossCursor`, including after the first anchor is dropped.

Rationale: drawing placement is already supported by preview geometry and interaction hints; the cursor should stay stable instead of changing per partial anchor count.

Alternative considered: introduce a second placement cursor after the first anchor is placed. That adds state complexity without strong additional clarity.

## Risks / Trade-offs

- [Risk] More cursor states can feel noisy if the precedence order is inconsistent. -> Mitigation: centralize the mapping in `_sync_cursor()` and explicitly test state precedence.
- [Risk] Directional cursor hints may be wrong for some drawing types if constraints are inferred too loosely. -> Mitigation: only apply directional cursors where the constraint is explicit and obvious.
- [Risk] Trade-link and order-line cursor behavior could regress while changing shared cursor logic. -> Mitigation: keep existing non-drawing behaviors intact and extend tests around interaction precedence.

## Migration Plan

1. Refactor cursor synchronization so drawing anchor hover, drawing body hover, and drag modes map separately.
2. Add constrained cursor handling for obvious vertical/horizontal edits.
3. Add tests covering browse, drawing, anchor hover, body hover, anchor drag, and body drag states.
4. No data migration or persistence updates are required.

## Open Questions

None for the first iteration. The initial scope is to improve clarity using standard Qt cursor shapes only.
