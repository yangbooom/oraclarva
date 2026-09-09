# Habitat UI design QA

## Comparison target

- Source visual truth path: `docs/assets/habitat-ui-reference.jpg`
- Implementation screenshot path: `docs/assets/habitat-ui-redroid.png`
- Source pixels: 1280 × 592
- Implementation pixels: 1280 × 592
- Viewport: 1280 × 592 landscape at 160 dpi
- Density normalization: 1 px per dp in the captured ReDroid profile
- State: native C++ simulation running; LIGHT selected; OBSERVE collapsed;
  light marker at normalized position (0.77, 0.39)
- Capture runtime: Android 13 ARM64 ReDroid container, ADB over loopback,
  ANGLE/SwiftShader software rendering

## Findings

No actionable P0, P1, or P2 findings remain in the checked viewport and state.

The concept image shows a more anatomically tapered and translucent organism
than the current native mesh can provide. The implementation intentionally
keeps the C++ 302-vertex/600-triangle body as the visible source instead of
baking the concept larva into the background. Its render-only projection was
matched to the concept's on-screen length, position, and diagonal orientation;
its geometry and motion remain native outputs.

## Required fidelity surfaces

- Fonts and typography: brand, tab, controls, rail labels, and causal badge
  preserve the condensed letter-spaced hierarchy without clipping or wrapping.
- Spacing and layout rhythm: the 66 dp header, 124 dp rail, selected tool card,
  bottom-right badge, and central organism remain separated at 1280 × 592.
- Colors and visual tokens: near-black chrome, mint selection, ivory text,
  coral body activation, muted disabled state, and warm light marker are
  preserved.
- Image quality and asset fidelity: the real raster habitat remains sharp and
  aspect-preserving. The organism is a live mesh, not part of the raster.
- Icons: official rounded Material Symbols replace host-dependent framework
  menu icons and now match the sun, grains, and three-object silhouettes.
- Copy and content: all fixed copy is visible. `release_validated=false` and
  the field → sense → body causal order stay present.
- Accessibility: primary controls expose descriptions and 44–48 dp targets;
  the disabled ground tool reports its limitation.

## Full-view comparison evidence

The reference and ReDroid capture were placed side by side at identical
1280 × 592 source dimensions. The comparison confirmed stable header
alignment, rail proportions, dish crop, live-mesh placement, and causal badge
position. The implementation's dish art is a source-cleaned illustrative
background rather than a reuse of the concept screenshot.

## Focused region comparison evidence

- Header: brand start, centered HABITAT tab/underline, and right controls align
  without crop or collision.
- Tool rail: selected LIGHT height, dividers, disabled GROUND treatment,
  OBSTACLE placement, and footer indicators align. Material Symbols remove the
  earlier semantic icon mismatch.
- Organism: final render projection matches the reference footprint and slope;
  native segment geometry remains visibly distinct from the concept artwork.
- Causal badge: the field/sense/body order and research-model line remain
  readable and clear of the dish rim.
- Observe state: the expanded live telemetry panel was captured separately;
  it remains within the viewport, does not cover the controls, and exposes the
  scientific claim boundary.

## Interaction evidence

- Pause changed its accessibility action from `Pause simulation` to
  `Resume simulation` and exposed `SIMULATION PAUSED`.
- Observe changed to `Hide simulation observation details` and exposed live
  C++ telemetry plus `no movement command`.
- A real drag changed the field readout from `Y +3240 · Z +1320` to
  `Y +1519 · Z +714`.
- Obstacle remained an enabled 141 dp tool target and invoked the existing
  two-millisecond posterior contact input.
- The app remained the top resumed activity after the 14,600-step fixture
  boundary and emitted no fatal Android runtime exception.

## Comparison history

- Iteration 0: blocked because the available Google Emulator binary could not
  run an ARM guest on this ARM host and no implementation pixels existed.
- Runtime iteration 1: ReDroid produced pixels and exposed a GLES shader error
  caused by whitespace before `#version`; shader source normalization fixed it.
- Runtime iteration 2: ReDroid exposed the reserved GLSL identifier `active`;
  it was renamed and covered by regression assertions.
- Runtime iteration 3: a 14,600-step fixture-limit crash returned to Launcher;
  Android now reads `maximum_steps` and resets before advancing past the
  validated fixture horizon.
- Visual iteration 1: the live body was too long, high, horizontal, and opaque.
  Render-only axial/radial scale, position, rotation, and alpha were corrected.
- Visual iteration 2: host-dependent framework icons did not match the source.
  Official Material Symbols were added and the final full/focused comparisons
  were re-run.

## Follow-up polish

- None required for the checked v1 landscape target. Alternate densities and
  physical-device GPU performance remain later validation gates, not blockers
  for this visual comparison.

final result: passed
