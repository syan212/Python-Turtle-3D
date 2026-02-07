"""
Controls:
    W/S         Rotate around X axis
    A/D         Rotate around Y axis
    Q/E         Rotate around Z axis
    Up/Down     Zoom in / out
    Left/Right  Pan horizontally
    PgUp/PgDn   Pan vertically
    R           Reset camera to default view
    Escape      Exit the renderer

Usage:
    main_lowLevel.py
"""

import math
import time
import turtle

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCREEN_WIDTH = 1200
SCREEN_HEIGHT = 800
SCREEN_BACKGROUND_COLOR = "lightblue"
SCREEN_TITLE = "Turtle 3D House — Low-Level"

PROJECTION_FOCAL_DISTANCE = 5.0
PROJECTION_SCALE_FACTOR = 100.0
NEAR_PLANE_EPSILON = 0.001

OFF_SCREEN_LIMIT = 8000
TARGET_FRAME_INTERVAL_SECONDS = 0.012  # ~83 FPS
IDLE_SLEEP_SECONDS = 0.001

DEFAULT_ROTATION_X = 0.450
DEFAULT_ROTATION_Y = 3.110
DEFAULT_ROTATION_Z = 0.000
DEFAULT_ZOOM_LEVEL = 0.340

ROTATION_INCREMENT = 0.01
ZOOM_INCREMENT = 0.1
PAN_INCREMENT = 5.0
INTERPOLATION_BLEND = 0.12
MINIMUM_ZOOM = 0.1

# HUD positioning
HUD_LEFT_COLUMN_X = -580
HUD_RIGHT_COLUMN_X = 350
HUD_TOP_ROW_Y = 350
HUD_ROW_HEIGHT = 20

HUD_FONT_TITLE = ("Arial", 16, "bold")
HUD_FONT_HEADING = ("Arial", 12, "bold")
HUD_FONT_BODY = ("Arial", 10, "normal")


# ---------------------------------------------------------------------------
# Global Mutable State
# ---------------------------------------------------------------------------

# Camera current values
camera_rotation_x = DEFAULT_ROTATION_X
camera_rotation_y = DEFAULT_ROTATION_Y
camera_rotation_z = DEFAULT_ROTATION_Z
camera_zoom = DEFAULT_ZOOM_LEVEL
camera_offset_x = 0.0
camera_offset_y = 0.0

# Camera interpolation targets
target_rotation_x = DEFAULT_ROTATION_X
target_rotation_y = DEFAULT_ROTATION_Y
target_rotation_z = DEFAULT_ROTATION_Z
target_zoom = DEFAULT_ZOOM_LEVEL
target_offset_x = 0.0
target_offset_y = 0.0

# Input tracking
held_keys: set[str] = set()

# Scene data — each entry: {"vertices": [...], "edges": [...], "color": str}
# Vertices are (x, y, z) float tuples; edges are (index_a, index_b) pairs.
scene_objects: list[dict] = []

# Turtle handles (initialised in setup_turtle_screen)
drawing_pen: turtle.Turtle | None = None
display_screen: turtle._Screen | None = None

# Animation flag
renderer_is_running = True


# ---------------------------------------------------------------------------
# Low-Level Vector Math (operates on raw 3-tuples)
# ---------------------------------------------------------------------------


def rotate_vertex_around_x(
    vertex: tuple[float, float, float],
    angle_radians: float,
) -> tuple[float, float, float]:
    """Rotate a (x, y, z) vertex around the X axis."""
    vx, vy, vz = vertex
    cos_a = math.cos(angle_radians)
    sin_a = math.sin(angle_radians)
    return (vx, vy * cos_a - vz * sin_a, vy * sin_a + vz * cos_a)


def rotate_vertex_around_y(
    vertex: tuple[float, float, float],
    angle_radians: float,
) -> tuple[float, float, float]:
    """Rotate a (x, y, z) vertex around the Y axis."""
    vx, vy, vz = vertex
    cos_a = math.cos(angle_radians)
    sin_a = math.sin(angle_radians)
    return (vx * cos_a + vz * sin_a, vy, -vx * sin_a + vz * cos_a)


def rotate_vertex_around_z(
    vertex: tuple[float, float, float],
    angle_radians: float,
) -> tuple[float, float, float]:
    """Rotate a (x, y, z) vertex around the Z axis."""
    vx, vy, vz = vertex
    cos_a = math.cos(angle_radians)
    sin_a = math.sin(angle_radians)
    return (vx * cos_a - vy * sin_a, vx * sin_a + vy * cos_a, vz)


def apply_camera_transform(
    vertex: tuple[float, float, float],
) -> tuple[float, float, float]:
    """Apply global camera rotation and zoom to a single vertex."""
    transformed = rotate_vertex_around_x(vertex, camera_rotation_x)
    transformed = rotate_vertex_around_y(transformed, camera_rotation_y)
    transformed = rotate_vertex_around_z(transformed, camera_rotation_z)
    tx, ty, tz = transformed
    return (tx * camera_zoom, ty * camera_zoom, tz * camera_zoom)


def project_vertex_to_screen(
    vertex: tuple[float, float, float],
) -> tuple[float, float]:
    """Perspective-project a camera-space vertex to 2D screen coordinates.

    Returns (0, 0) if the vertex sits at or behind the near plane.
    """
    _, _, vz = vertex
    denominator = vz + PROJECTION_FOCAL_DISTANCE
    if abs(denominator) < NEAR_PLANE_EPSILON:
        return (0.0, 0.0)
    perspective_factor = PROJECTION_FOCAL_DISTANCE / denominator
    screen_x = vertex[0] * perspective_factor * PROJECTION_SCALE_FACTOR
    screen_y = vertex[1] * perspective_factor * PROJECTION_SCALE_FACTOR
    return (screen_x, screen_y)


# ---------------------------------------------------------------------------
# Mesh Construction Helpers
# ---------------------------------------------------------------------------


def create_box_mesh(
    center_x: float,
    base_y: float,
    center_z: float,
    width: float,
    height: float,
    depth: float,
    color: str,
) -> dict:
    """Return a wireframe box dict (vertices + edges) with bottom at base_y."""
    half_w = width / 2.0
    half_d = depth / 2.0

    vertices = [
        # Bottom face (indices 0-3)
        (center_x - half_w, base_y, center_z - half_d),
        (center_x + half_w, base_y, center_z - half_d),
        (center_x + half_w, base_y, center_z + half_d),
        (center_x - half_w, base_y, center_z + half_d),
        # Top face (indices 4-7)
        (center_x - half_w, base_y + height, center_z - half_d),
        (center_x + half_w, base_y + height, center_z - half_d),
        (center_x + half_w, base_y + height, center_z + half_d),
        (center_x - half_w, base_y + height, center_z + half_d),
    ]
    edges = [
        (0, 1),
        (1, 2),
        (2, 3),
        (3, 0),  # bottom
        (4, 5),
        (5, 6),
        (6, 7),
        (7, 4),  # top
        (0, 4),
        (1, 5),
        (2, 6),
        (3, 7),  # vertical pillars
    ]
    return {"vertices": vertices, "edges": edges, "color": color}


def create_prism_roof_mesh(
    center_x: float,
    base_y: float,
    center_z: float,
    width: float,
    peak_height: float,
    depth: float,
    color: str,
    ridge_along_z: bool = True,
) -> dict:
    """Return a triangular-prism roof dict.

    *ridge_along_z=True*  — ridge line is parallel to the Z axis.
    *ridge_along_z=False* — ridge line is parallel to the X axis.
    """
    half_w = width / 2.0
    half_d = depth / 2.0

    base_verts = [
        (center_x - half_w, base_y, center_z - half_d),
        (center_x + half_w, base_y, center_z - half_d),
        (center_x + half_w, base_y, center_z + half_d),
        (center_x - half_w, base_y, center_z + half_d),
    ]

    if ridge_along_z:
        ridge_verts = [
            (center_x, base_y + peak_height, center_z - half_d),
            (center_x, base_y + peak_height, center_z + half_d),
        ]
        slope_edges = [(0, 4), (1, 4), (2, 5), (3, 5)]
    else:
        ridge_verts = [
            (center_x - half_w, base_y + peak_height, center_z),
            (center_x + half_w, base_y + peak_height, center_z),
        ]
        slope_edges = [(0, 4), (3, 4), (1, 5), (2, 5)]

    vertices = base_verts + ridge_verts
    edges = [
        (0, 1),
        (1, 2),
        (2, 3),
        (3, 0),  # base rectangle
        *slope_edges,  # slopes
        (4, 5),  # ridge line
    ]
    return {"vertices": vertices, "edges": edges, "color": color}


# ---------------------------------------------------------------------------
# Composite Building Helpers (append directly to scene_objects)
# ---------------------------------------------------------------------------


def add_standard_house(
    position_x: float,
    position_z: float,
    wall_color: str = "saddlebrown",
    roof_color: str = "darkred",
) -> None:
    """Append a house (walls, roof, door, two windows) to the scene."""
    scene_objects.append(
        create_box_mesh(position_x, 0, position_z, 5, 2.5, 5, wall_color)
    )
    scene_objects.append(
        create_prism_roof_mesh(position_x, 2.5, position_z, 5.4, 1.3, 5.4, roof_color)
    )
    front_z = position_z + 2.51
    # Door
    scene_objects.append(
        create_box_mesh(position_x, 0, front_z, 1.0, 1.8, 0.1, "darkgreen")
    )
    # Left window
    scene_objects.append(
        create_box_mesh(position_x - 1.25, 0.5, front_z, 1.0, 1.0, 0.1, "lightblue")
    )
    # Right window
    scene_objects.append(
        create_box_mesh(position_x + 1.25, 0.5, front_z, 1.0, 1.0, 0.1, "lightblue")
    )


def add_shop_building(
    position_x: float,
    position_z: float,
    wall_color: str = "firebrick",
) -> None:
    """Append a flat-roofed shop with sign, windows, and door."""
    wall_height = 3.0
    scene_objects.append(
        create_box_mesh(position_x, 0, position_z, 7, wall_height, 6, wall_color)
    )
    # Flat roof cap
    scene_objects.append(
        create_box_mesh(position_x, wall_height, position_z, 7.4, 0.2, 6.4, "dimgray")
    )
    front_z = position_z + 3.0
    # Sign
    scene_objects.append(
        create_box_mesh(position_x, 3.5, front_z, 4, 0.8, 0.1, "wheat")
    )
    # Display windows
    scene_objects.append(
        create_box_mesh(position_x - 2, 0.5, front_z + 0.01, 2.5, 2.0, 0.1, "cyan")
    )
    scene_objects.append(
        create_box_mesh(position_x + 2, 0.5, front_z + 0.01, 2.5, 2.0, 0.1, "cyan")
    )
    # Door
    scene_objects.append(
        create_box_mesh(position_x, 0, front_z + 0.01, 1.2, 2.2, 0.1, "black")
    )


def add_tree(position_x: float, position_z: float) -> None:
    """Append a simple tree (trunk box + triangular canopy)."""
    scene_objects.append(
        create_box_mesh(position_x, 0, position_z, 0.5, 1.5, 0.5, "saddlebrown")
    )
    scene_objects.append(
        create_prism_roof_mesh(
            position_x, 1.5, position_z, 2.5, 3, 2.5, "forestgreen", ridge_along_z=True
        )
    )


# ---------------------------------------------------------------------------
# Scene Assembly
# ---------------------------------------------------------------------------


def build_full_scene() -> None:
    """Populate *scene_objects* with every mesh in the suburban neighbourhood."""
    scene_objects.clear()

    # --- Main house with porch, chimney, and garage -----------------------
    add_standard_house(0, 0)
    # Porch platform and posts
    scene_objects.append(create_box_mesh(0, 0, 2.8, 2.0, 0.1, 1.5, "tan"))
    scene_objects.append(create_box_mesh(-0.8, 0, 3.4, 0.2, 2.0, 0.2, "tan"))
    scene_objects.append(create_box_mesh(0.8, 0, 3.4, 0.2, 2.0, 0.2, "tan"))
    # Chimney
    scene_objects.append(create_box_mesh(1.5, 2.0, -1.5, 0.8, 2.5, 0.8, "gray"))
    # Garage
    scene_objects.append(create_box_mesh(4.25, 0, 0, 3.5, 2.0, 4.5, "saddlebrown"))
    scene_objects.append(create_prism_roof_mesh(4.25, 2.0, 0, 3.9, 1.0, 4.9, "darkred"))
    scene_objects.append(
        create_box_mesh(4.25, 0, 2.26, 2.8, 1.8, 0.1, "white")
    )  # garage door

    # --- Driveway and footpath --------------------------------------------
    scene_objects.append(create_box_mesh(4.25, 0.02, 5.25, 3.0, 0, 5.5, "gray"))
    scene_objects.append(create_box_mesh(0, 0.02, 5.0, 1.2, 0, 5.0, "lightgray"))

    # --- Streets and lane markings ----------------------------------------
    scene_objects.append(create_box_mesh(0, 0.01, 8, 100, 0, 4, "dimgray"))
    scene_objects.append(create_box_mesh(-20, 0.01, 8, 4, 0, 40, "dimgray"))
    for stripe_index in range(-15, 16):
        scene_objects.append(
            create_box_mesh(stripe_index * 5, 0.02, 8, 2, 0, 0.2, "yellow")
        )

    # --- Neighbour houses -------------------------------------------------
    neighbour_configs = [
        (-15, "tan", "black"),
        (-7, "indianred", "maroon"),
        (15, "goldenrod", "chocolate"),
    ]
    for house_x, wall_color, roof_color in neighbour_configs:
        add_standard_house(house_x, 15, wall_color, roof_color)
        scene_objects.append(
            create_box_mesh(house_x, 0.02, 11.5, 1.2, 0, 3, "lightgray")
        )

    # --- Shops ------------------------------------------------------------
    add_shop_building(-25, 8)
    add_shop_building(-33, 8)

    # --- Trees ------------------------------------------------------------
    tree_positions = [(-5, 5), (5, 5), (-12, 12), (12, 12), (-20, 10)]
    for tree_x, tree_z in tree_positions:
        add_tree(tree_x, tree_z)

    # --- Origin axis indicator (debugging) --------------------------------
    scene_objects.append(create_box_mesh(0, 0, 0, 1, 0.1, 0.1, "red"))


# ---------------------------------------------------------------------------
# Turtle / Screen Setup
# ---------------------------------------------------------------------------


def setup_turtle_screen() -> None:
    """Initialise the turtle window and drawing pen."""
    global display_screen, drawing_pen

    display_screen = turtle.Screen()
    display_screen.bgcolor(SCREEN_BACKGROUND_COLOR)
    display_screen.title(SCREEN_TITLE)
    display_screen.setup(SCREEN_WIDTH, SCREEN_HEIGHT)
    display_screen.tracer(0)

    drawing_pen = turtle.Turtle()
    drawing_pen.speed(0)
    drawing_pen.pensize(1)
    drawing_pen.hideturtle()


# ---------------------------------------------------------------------------
# Input Binding
# ---------------------------------------------------------------------------


def bind_keyboard_controls() -> None:
    """Register all key press / release handlers on the display screen."""
    display_screen.listen()

    continuous_keys = [
        "w",
        "s",
        "a",
        "d",
        "q",
        "e",
        "Up",
        "Down",
        "Left",
        "Right",
        "Page_Up",
        "Page_Down",
    ]
    for key_name in continuous_keys:
        # Closure trick: default argument captures current key_name
        display_screen.onkeypress(lambda k=key_name: held_keys.add(k), key_name)
        display_screen.onkeyrelease(lambda k=key_name: held_keys.discard(k), key_name)

    display_screen.onkey(reset_camera_to_defaults, "r")
    display_screen.onkey(request_exit, "Escape")


# ---------------------------------------------------------------------------
# Camera Control
# ---------------------------------------------------------------------------


def reset_camera_to_defaults() -> None:
    """Set interpolation targets back to the default viewing angle."""
    global target_rotation_x, target_rotation_y, target_rotation_z
    global target_zoom, target_offset_x, target_offset_y

    target_rotation_x = DEFAULT_ROTATION_X
    target_rotation_y = DEFAULT_ROTATION_Y
    target_rotation_z = DEFAULT_ROTATION_Z
    target_zoom = DEFAULT_ZOOM_LEVEL
    target_offset_x = 0.0
    target_offset_y = 0.0


def apply_held_keys_to_targets() -> None:
    """Adjust camera targets based on currently pressed keys."""
    global target_rotation_x, target_rotation_y, target_rotation_z
    global target_zoom, target_offset_x, target_offset_y

    # Rotation
    if "w" in held_keys:
        target_rotation_x += ROTATION_INCREMENT
    if "s" in held_keys:
        target_rotation_x -= ROTATION_INCREMENT
    if "d" in held_keys:
        target_rotation_y += ROTATION_INCREMENT
    if "a" in held_keys:
        target_rotation_y -= ROTATION_INCREMENT
    if "e" in held_keys:
        target_rotation_z += ROTATION_INCREMENT
    if "q" in held_keys:
        target_rotation_z -= ROTATION_INCREMENT

    # Zoom
    if "Up" in held_keys:
        target_zoom = max(MINIMUM_ZOOM, target_zoom + ZOOM_INCREMENT)
    if "Down" in held_keys:
        target_zoom = max(MINIMUM_ZOOM, target_zoom - ZOOM_INCREMENT)

    # Pan
    if "Right" in held_keys:
        target_offset_x += PAN_INCREMENT
    if "Left" in held_keys:
        target_offset_x -= PAN_INCREMENT
    if "Page_Up" in held_keys:
        target_offset_y += PAN_INCREMENT
    if "Page_Down" in held_keys:
        target_offset_y -= PAN_INCREMENT


def interpolate_camera_toward_targets() -> None:
    """Smoothly blend current camera values toward their targets."""
    global camera_rotation_x, camera_rotation_y, camera_rotation_z
    global camera_zoom, camera_offset_x, camera_offset_y

    blend = INTERPOLATION_BLEND
    camera_rotation_x += (target_rotation_x - camera_rotation_x) * blend
    camera_rotation_y += (target_rotation_y - camera_rotation_y) * blend
    camera_rotation_z += (target_rotation_z - camera_rotation_z) * blend
    camera_zoom += (target_zoom - camera_zoom) * blend
    camera_offset_x += (target_offset_x - camera_offset_x) * blend
    camera_offset_y += (target_offset_y - camera_offset_y) * blend


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------


def draw_edge_between_vertices(
    vertex_a: tuple[float, float, float],
    vertex_b: tuple[float, float, float],
    color: str,
) -> None:
    """Transform, project, and draw a single wireframe edge."""
    transformed_a = apply_camera_transform(vertex_a)
    transformed_b = apply_camera_transform(vertex_b)

    screen_ax, screen_ay = project_vertex_to_screen(transformed_a)
    screen_bx, screen_by = project_vertex_to_screen(transformed_b)

    # Cull edges projected far off screen
    if (
        abs(screen_ax) > OFF_SCREEN_LIMIT
        or abs(screen_ay) > OFF_SCREEN_LIMIT
        or abs(screen_bx) > OFF_SCREEN_LIMIT
        or abs(screen_by) > OFF_SCREEN_LIMIT
    ):
        return

    # Apply pan offset
    final_ax = screen_ax + camera_offset_x
    final_ay = screen_ay + camera_offset_y
    final_bx = screen_bx + camera_offset_x
    final_by = screen_by + camera_offset_y

    try:
        drawing_pen.color(color)
        drawing_pen.penup()
        drawing_pen.goto(final_ax, final_ay)
        drawing_pen.pendown()
        drawing_pen.goto(final_bx, final_by)
    except turtle.Terminator:
        pass  # Window closed mid-draw


def compute_average_depth(mesh: dict) -> float:
    """Return mean transformed Z across all vertices in a mesh."""
    vertices = mesh["vertices"]
    total_z = sum(apply_camera_transform(v)[2] for v in vertices)
    return total_z / len(vertices)


def draw_all_scene_objects() -> None:
    """Depth-sort and draw every object in the global scene list."""
    sorted_objects = sorted(scene_objects, key=compute_average_depth, reverse=True)

    for mesh in sorted_objects:
        vertices = mesh["vertices"]
        color = mesh["color"]
        for index_a, index_b in mesh["edges"]:
            if index_a < len(vertices) and index_b < len(vertices):
                draw_edge_between_vertices(vertices[index_a], vertices[index_b], color)


# ---------------------------------------------------------------------------
# Heads-Up Display
# ---------------------------------------------------------------------------


def write_text_at(
    x: float,
    y: float,
    text: str,
    font: tuple = HUD_FONT_BODY,
) -> None:
    """Write a string at an absolute screen position."""
    drawing_pen.penup()
    drawing_pen.goto(x, y)
    drawing_pen.color("black")
    drawing_pen.write(text, font=font)


def draw_heads_up_display() -> None:
    """Render control hints and camera telemetry on the canvas."""
    # -- Left column: title and controls -----------------------------------
    col_x = HUD_LEFT_COLUMN_X
    row_y = HUD_TOP_ROW_Y

    write_text_at(col_x, row_y, "3D Rendered House", HUD_FONT_TITLE)
    row_y -= HUD_ROW_HEIGHT + 10
    write_text_at(
        col_x, row_y, "Movement Controls (Hold for continuous):", HUD_FONT_HEADING
    )

    control_hints = [
        "WASD: Rotate around X and Y axes",
        "QE: Rotate around Z axis",
        "Up/Down arrows: Zoom in/out",
        "Left/Right arrows: Pan left/right",
        "PgUp/PgDn: Pan up/down",
        "R: Reset view",
        "ESC: Exit",
    ]
    for hint_line in control_hints:
        row_y -= HUD_ROW_HEIGHT
        write_text_at(col_x, row_y, hint_line)

    # -- Right column: camera telemetry ------------------------------------
    col_x = HUD_RIGHT_COLUMN_X
    row_y = HUD_TOP_ROW_Y

    write_text_at(col_x, row_y, "Camera Status:", HUD_FONT_HEADING)
    telemetry_lines = [
        f"Rotation X: {camera_rotation_x:.3f}",
        f"Rotation Y: {camera_rotation_y:.3f}",
        f"Rotation Z: {camera_rotation_z:.3f}",
        f"Zoom: {camera_zoom:.3f}",
        f"Objects: {len(scene_objects)}",
    ]
    for line in telemetry_lines:
        row_y -= HUD_ROW_HEIGHT
        write_text_at(col_x, row_y, line)


# ---------------------------------------------------------------------------
# Frame Rendering
# ---------------------------------------------------------------------------


def render_single_frame() -> None:
    """Execute one complete frame: input -> update -> draw -> flip."""
    apply_held_keys_to_targets()
    interpolate_camera_toward_targets()
    drawing_pen.clear()
    draw_all_scene_objects()
    draw_heads_up_display()
    display_screen.update()


# ---------------------------------------------------------------------------
# Main Loop
# ---------------------------------------------------------------------------


def request_exit() -> None:
    """Signal the animation loop to stop."""
    global renderer_is_running
    renderer_is_running = False


def run_animation_loop() -> None:
    """Block on the main render loop until the user exits."""
    global renderer_is_running
    previous_frame_time = time.time()

    while renderer_is_running:
        current_time = time.time()
        elapsed_seconds = current_time - previous_frame_time

        if elapsed_seconds >= TARGET_FRAME_INTERVAL_SECONDS:
            render_single_frame()
            previous_frame_time = current_time
        else:
            time.sleep(IDLE_SLEEP_SECONDS)

    display_screen.bye()


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------


def main() -> None:
    """Print usage instructions, build the scene, and start the renderer."""
    instructions = [
        "Starting 3D Suburban Scene Renderer (Low-Level)...",
        "",
        "Controls (hold keys for continuous movement):",
        "  W/S         Rotate around X axis",
        "  A/D         Rotate around Y axis",
        "  Q/E         Rotate around Z axis",
        "  Up/Down     Zoom in / out",
        "  Left/Right  Pan horizontally",
        "  PgUp/PgDn   Pan vertically",
        "  R           Reset view",
        "  Escape      Exit",
        "",
        "Click on the graphics window to give it focus, then use the controls.",
    ]
    print("\n".join(instructions))

    setup_turtle_screen()
    build_full_scene()
    bind_keyboard_controls()
    run_animation_loop()


if __name__ == "__main__":
    main()
