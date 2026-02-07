Two implementations are provided that produce identical output but follow fundamentally different code-organisation philosophies.

| File | Style | Key Abstractions |
|---|---|---|
| `main_highLevel.py` | Object-oriented | `dataclass`, `NamedTuple`, `Enum`, dedicated classes |
| `main_lowLevel.py` | Procedural | Plain tuples, dictionaries, module-level functions and globals |

---

## Table of Contents

1. [Requirements](#requirements)
2. [Quick Start](#quick-start)
3. [Controls](#controls)
4. [Architecture Overview](#architecture-overview)
   - [High-Level Version](#high-level-version-main_highlevelpy)
   - [Low-Level Version](#low-level-version-main_lowlevelpy)
5. [Rendering Pipeline](#rendering-pipeline)
6. [Scene Composition](#scene-composition)
7. [Configuration Constants](#configuration-constants)
8. [Extending the Scene](#extending-the-scene)
9. [Design Decisions](#design-decisions)

---

## Requirements

- **Python 3.10+** (uses `match` style type unions and `slots=True` on dataclasses)
- **`turtle` module** — included in the Python standard library (no additional packages needed)
- A graphical display environment (the `turtle` module requires a GUI-capable system)

---

## Quick Start

```bash
# Run the high-level (object-oriented) version
python main_highLevel.py

# Run the low-level (procedural) version
python main_lowLevel.py
```

Both commands open a **1200 x 800** window with a light-blue background. Click inside the window to give it keyboard focus, then use the controls listed below.

---

## Controls

All movement keys support **continuous hold** — press and hold a key for smooth, uninterrupted camera movement.

| Key(s) | Action |
|---|---|
| `W` / `S` | Rotate around the **X** axis (pitch up / down) |
| `A` / `D` | Rotate around the **Y** axis (yaw left / right) |
| `Q` / `E` | Rotate around the **Z** axis (roll left / right) |
| `Up` / `Down` Arrow | Zoom **in** / **out** |
| `Left` / `Right` Arrow | Pan **left** / **right** |
| `Page Up` / `Page Down` | Pan **up** / **down** |
| `R` | Reset camera to the default viewing angle |
| `Escape` | Exit the renderer |

Camera transitions are **smoothly interpolated** — the current camera state blends toward the target at a configurable rate (default: 12% per frame), producing fluid movement.

---

## Architecture Overview

### High-Level Version (`main_highLevel.py`)

This version uses Python's object-oriented features to separate concerns into well-defined, self-contained units.

#### Core Types

| Type | Kind | Purpose |
|---|---|---|
| `Vector3` | `@dataclass(frozen=True, slots=True)` | Immutable 3D point with rotation and projection methods |
| `ScreenPoint` | `NamedTuple` | 2D screen-space coordinate after projection |
| `RidgeAxis` | `Enum` | Determines the direction of a roof's ridge line (`X` or `Z`) |
| `WireframeObject` | `@dataclass` | A coloured wireframe mesh (vertices + edge index-pairs) |
| `CameraState` | `@dataclass` | Current and target values for rotation, zoom, and pan offset |

#### Classes

| Class | Responsibility |
|---|---|
| `SuburbanSceneBuilder` | Factory that constructs all 3D meshes (houses, shops, streets, trees) and returns them as a list of `WireframeObject` instances |
| `InputHandler` | Translates held keyboard keys into adjustments on `CameraState` targets |
| `HeadsUpDisplay` | Renders the on-screen text overlay (control hints and camera telemetry) |
| `SuburbanSceneRenderer` | Top-level orchestrator — owns the turtle screen, camera, input handler, HUD, and frame loop |

#### Call Graph

```
main()
  └─ SuburbanSceneRenderer()
       ├─ SuburbanSceneBuilder.build()    → list[WireframeObject]
       ├─ InputHandler.bind_all_controls()
       └─ .run()                          → frame loop
            └─ _render_single_frame()
                 ├─ InputHandler.apply_held_keys_to_camera()
                 ├─ CameraState.interpolate_toward_targets()
                 ├─ _draw_all_objects()
                 │    └─ _draw_edge_3d()
                 │         ├─ CameraState.transform_vertex()
                 │         └─ Vector3.project_to_screen()
                 ├─ HeadsUpDisplay.draw()
                 └─ screen.update()
```

---

### Low-Level Version (`main_lowLevel.py`)

This version achieves the same result with a flat, procedural style. There are **no classes** — all state is module-level, all geometry is stored in plain tuples and dictionaries, and all logic is expressed as standalone functions.

#### Data Representations

| Concept | Representation |
|---|---|
| 3D vertex | `tuple[float, float, float]` (e.g. `(1.0, 2.5, -3.0)`) |
| 2D screen point | `tuple[float, float]` |
| Wireframe mesh | `dict` with keys `"vertices"`, `"edges"`, `"color"` |
| Scene | `list[dict]` stored in the module-level variable `scene_objects` |
| Camera state | Six module-level floats (`camera_rotation_x`, `camera_zoom`, etc.) |
| Input state | A module-level `set[str]` named `held_keys` |

#### Key Functions

| Function | Purpose |
|---|---|
| `rotate_vertex_around_x/y/z()` | Apply a rotation matrix to a single `(x, y, z)` tuple |
| `apply_camera_transform()` | Chain all three rotations + zoom on a vertex |
| `project_vertex_to_screen()` | Perspective-project a 3D vertex to 2D screen coordinates |
| `create_box_mesh()` | Return a wireframe box `dict` (8 vertices, 12 edges) |
| `create_prism_roof_mesh()` | Return a triangular prism `dict` (6 vertices, 9 edges) |
| `add_standard_house()` | Append a full house (walls, roof, door, windows) to `scene_objects` |
| `add_shop_building()` | Append a shop (flat roof, sign, windows, door) to `scene_objects` |
| `add_tree()` | Append a tree (trunk + canopy) to `scene_objects` |
| `build_full_scene()` | Assemble the entire suburban neighbourhood |
| `apply_held_keys_to_targets()` | Read `held_keys` and adjust camera targets |
| `interpolate_camera_toward_targets()` | Blend current camera values toward targets |
| `draw_edge_between_vertices()` | Transform, project, and draw one wireframe edge |
| `draw_all_scene_objects()` | Depth-sort and render the entire scene |
| `draw_heads_up_display()` | Render the HUD text overlay |
| `render_single_frame()` | Execute one complete frame cycle |
| `run_animation_loop()` | Block on the main loop until exit |

#### Call Graph

```
main()
  ├─ setup_turtle_screen()
  ├─ build_full_scene()
  │    ├─ add_standard_house()  → create_box_mesh(), create_prism_roof_mesh()
  │    ├─ add_shop_building()   → create_box_mesh()
  │    └─ add_tree()            → create_box_mesh(), create_prism_roof_mesh()
  ├─ bind_keyboard_controls()
  └─ run_animation_loop()
       └─ render_single_frame()
            ├─ apply_held_keys_to_targets()
            ├─ interpolate_camera_toward_targets()
            ├─ draw_all_scene_objects()
            │    └─ draw_edge_between_vertices()
            │         ├─ apply_camera_transform()
            │         │    └─ rotate_vertex_around_x/y/z()
            │         └─ project_vertex_to_screen()
            ├─ draw_heads_up_display()
            └─ screen.update()
```

---

## Rendering Pipeline

Both versions follow the same per-frame pipeline:

1. **Input Processing** — Read the set of currently held keys and update camera *target* values (rotation, zoom, pan).
2. **Camera Interpolation** — Linearly blend the *current* camera state toward the *target* state by a fixed factor (default `0.12`), producing smooth transitions.
3. **Clear Canvas** — Erase the previous frame from the turtle canvas.
4. **Depth Sort** — Compute the mean transformed Z-depth of each mesh and sort from farthest to nearest (painter's algorithm).
5. **Edge Drawing** — For each mesh (back-to-front), iterate over its edge list. For each edge:
   - Apply X, Y, Z rotation matrices and uniform zoom to both endpoint vertices.
   - Perspective-project the transformed vertices onto 2D screen coordinates using a simple focal-distance model.
   - Cull the edge if either endpoint projects beyond the off-screen threshold.
   - Apply the camera pan offset and draw the line segment with the turtle pen.
6. **HUD Overlay** — Write control hints and live camera telemetry as text on the canvas.
7. **Screen Update** — Flip the double buffer (`screen.update()`) and proceed to the next frame.

The target frame interval is **~12 ms** (approximately 83 FPS). When the loop finishes a frame early, it sleeps for 1 ms to avoid busy-waiting.

---

## Scene Composition

The suburban neighbourhood is composed of the following elements:

| Element | Count | Description |
|---|---|---|
| Main house | 1 | Standard house at the origin with a front porch (platform + two posts) and a chimney |
| Garage | 1 | Attached to the main house with a triangular roof and a white garage door |
| Neighbour houses | 3 | Positioned across the main street with unique wall/roof colour schemes |
| Shops | 2 | Flat-roofed commercial buildings with storefronts, display windows, signs, and doors |
| Main street | 1 | A long horizontal road with yellow centre-line stripe markings |
| Cross street | 1 | A perpendicular road intersecting the main street |
| Driveway | 1 | Connects the garage to the main street |
| Footpaths | 4 | Walkways from each house to the street |
| Trees | 5 | Simple box trunk + triangular prism canopy scattered around the neighbourhood |
| Origin marker | 1 | A small red box at `(0, 0, 0)` for debugging and orientation reference |

---

## Configuration Constants

All tunable values are defined as module-level constants at the top of each file for easy adjustment.

### Display

| Constant | Default | Description |
|---|---|---|
| `SCREEN_WIDTH` | `1200` | Window width in pixels |
| `SCREEN_HEIGHT` | `800` | Window height in pixels |
| `SCREEN_BACKGROUND_COLOR` | `"lightblue"` | Canvas background colour |

### Projection

| Constant | Default | Description |
|---|---|---|
| `PROJECTION_DISTANCE` / `PROJECTION_FOCAL_DISTANCE` | `5.0` | Focal distance for the perspective projection |
| `PROJECTION_SCALE` / `PROJECTION_SCALE_FACTOR` | `100.0` | Multiplier applied after perspective division |
| `NEAR_PLANE_EPSILON` | `0.001` | Minimum denominator to prevent division-by-zero |

### Camera Defaults

| Constant | Default | Description |
|---|---|---|
| `DEFAULT_ROTATION_X` | `0.450` | Initial X-axis rotation (radians) |
| `DEFAULT_ROTATION_Y` | `3.110` | Initial Y-axis rotation (radians) |
| `DEFAULT_ROTATION_Z` | `0.000` | Initial Z-axis rotation (radians) |
| `DEFAULT_ZOOM` / `DEFAULT_ZOOM_LEVEL` | `0.340` | Initial zoom factor |

### Movement

| Constant | Default | Description |
|---|---|---|
| `ROTATION_SPEED` / `ROTATION_INCREMENT` | `0.01` | Radians added per frame while a rotation key is held |
| `ZOOM_SPEED` / `ZOOM_INCREMENT` | `0.1` | Zoom delta per frame |
| `PAN_SPEED` / `PAN_INCREMENT` | `5.0` | Pixel offset per frame |
| `SMOOTHING_FACTOR` / `INTERPOLATION_BLEND` | `0.12` | Linear interpolation blend rate (0 = no movement, 1 = instant) |
| `MIN_ZOOM` / `MINIMUM_ZOOM` | `0.1` | Floor value preventing the zoom from reaching zero or going negative |

---

## Extending the Scene

### Adding a New Object

**High-level version** — add a method to `SuburbanSceneBuilder`:

```python
def _build_park_bench(self) -> None:
    """Add a park bench at the given location."""
    self._add_box(10, 0, 5, 2.0, 0.5, 0.8, "sienna")   # seat
    self._add_box(10, 0, 5, 2.0, 1.0, 0.1, "sienna")    # backrest
```

Then call it from `build()`.

**Low-level version** — create a new builder function:

```python
def add_park_bench(position_x: float, position_z: float) -> None:
    """Append a park bench to scene_objects."""
    scene_objects.append(create_box_mesh(position_x, 0, position_z, 2.0, 0.5, 0.8, "sienna"))
    scene_objects.append(create_box_mesh(position_x, 0, position_z, 2.0, 1.0, 0.1, "sienna"))
```

Then call it from `build_full_scene()`.

### Adding a New Control

1. Add the key string (e.g. `"space"`) to the continuous-keys list in the input binding section.
2. Add a corresponding `if "space" in held_keys:` block in the held-keys handler that modifies the appropriate camera target variable.

---

## Design Decisions

| Decision | Rationale |
|---|---|
| **`turtle` graphics** | Requires zero external dependencies — ships with every standard Python installation. Ideal for educational and prototyping purposes. |
| **Painter's algorithm** | Simple back-to-front depth sorting is sufficient for non-overlapping wireframe meshes and avoids the complexity of a Z-buffer. |
| **Smooth interpolation** | Exponential easing (`current += (target - current) * blend`) makes all camera movements feel fluid without requiring complex easing curves. |
| **Held-key set** | Tracking keys in a `set` (rather than using single key-press callbacks) enables simultaneous multi-axis movement. |
| **Two versions** | Providing both OOP and procedural implementations demonstrates how the same rendering logic can be expressed at different levels of abstraction, making the project useful as a learning resource. |
