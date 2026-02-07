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
    python main_highLevel.py
"""

from __future__ import annotations

import math
import time
import turtle
from dataclasses import dataclass
from enum import Enum, auto
from typing import NamedTuple


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCREEN_WIDTH = 1200
SCREEN_HEIGHT = 800
SCREEN_BACKGROUND_COLOR = "lightblue"
SCREEN_TITLE = "Turtle 3D House — High-Level"

PROJECTION_DISTANCE = 5
PROJECTION_SCALE = 100
PROJECTION_NEAR_PLANE_EPSILON = 0.001

OFF_SCREEN_THRESHOLD = 8000
TARGET_FRAME_INTERVAL = 0.012  # ~83 FPS
IDLE_SLEEP_SECONDS = 0.001

# Default camera state
DEFAULT_ROTATION_X = 0.450
DEFAULT_ROTATION_Y = 3.110
DEFAULT_ROTATION_Z = 0.000
DEFAULT_ZOOM = 0.340

ROTATION_SPEED = 0.01
ZOOM_SPEED = 0.1
PAN_SPEED = 5
SMOOTHING_FACTOR = 0.12
MIN_ZOOM = 0.1

# HUD layout
HUD_LEFT_X = -580
HUD_RIGHT_X = 350
HUD_TOP_Y = 350
HUD_LINE_SPACING = 20
HUD_FONT_TITLE = ("Arial", 16, "bold")
HUD_FONT_HEADING = ("Arial", 12, "bold")
HUD_FONT_BODY = ("Arial", 10, "normal")


# ---------------------------------------------------------------------------
# Geometry Primitives
# ---------------------------------------------------------------------------


class ScreenPoint(NamedTuple):
    """A 2D point in screen-space pixel coordinates."""

    x: float
    y: float


@dataclass(frozen=True, slots=True)
class Vector3:
    """An immutable point or direction in 3D space.

    Provides rotation helpers for each principal axis using standard
    rotation matrices, and a perspective projection to screen coordinates.
    """

    x: float
    y: float
    z: float

    # -- Rotations (return new Vector3, original is unchanged) -------------

    def rotated_around_x(self, angle_radians: float) -> Vector3:
        """Rotate this vector around the X axis by *angle_radians*."""
        cos_angle = math.cos(angle_radians)
        sin_angle = math.sin(angle_radians)
        new_y = self.y * cos_angle - self.z * sin_angle
        new_z = self.y * sin_angle + self.z * cos_angle
        return Vector3(self.x, new_y, new_z)

    def rotated_around_y(self, angle_radians: float) -> Vector3:
        """Rotate this vector around the Y axis by *angle_radians*."""
        cos_angle = math.cos(angle_radians)
        sin_angle = math.sin(angle_radians)
        new_x = self.x * cos_angle + self.z * sin_angle
        new_z = -self.x * sin_angle + self.z * cos_angle
        return Vector3(new_x, self.y, new_z)

    def rotated_around_z(self, angle_radians: float) -> Vector3:
        """Rotate this vector around the Z axis by *angle_radians*."""
        cos_angle = math.cos(angle_radians)
        sin_angle = math.sin(angle_radians)
        new_x = self.x * cos_angle - self.y * sin_angle
        new_y = self.x * sin_angle + self.y * cos_angle
        return Vector3(new_x, new_y, self.z)

    def scaled(self, factor: float) -> Vector3:
        """Return a uniformly scaled copy of this vector."""
        return Vector3(self.x * factor, self.y * factor, self.z * factor)

    # -- Projection --------------------------------------------------------

    def project_to_screen(
        self,
        focal_distance: float = PROJECTION_DISTANCE,
    ) -> ScreenPoint:
        """Perspective-project this 3D point onto 2D screen coordinates.

        Returns (0, 0) when the point is at or behind the near plane to
        prevent division-by-zero artefacts.
        """
        denominator = self.z + focal_distance
        if abs(denominator) < PROJECTION_NEAR_PLANE_EPSILON:
            return ScreenPoint(0.0, 0.0)
        perspective_factor = focal_distance / denominator
        return ScreenPoint(
            self.x * perspective_factor * PROJECTION_SCALE,
            self.y * perspective_factor * PROJECTION_SCALE,
        )


# ---------------------------------------------------------------------------
# Scene Object
# ---------------------------------------------------------------------------


class RidgeAxis(Enum):
    """Determines which axis a triangular-prism ridge runs along."""

    X = auto()
    Z = auto()


@dataclass
class WireframeObject:
    """A colored wireframe mesh defined by vertices and edge index-pairs."""

    vertices: list[Vector3]
    edges: list[tuple[int, int]]
    color: str


# ---------------------------------------------------------------------------
# Scene Builder — creates the suburban neighborhood
# ---------------------------------------------------------------------------


class SuburbanSceneBuilder:
    """Factory that constructs all 3D objects for the suburban scene."""

    def __init__(self) -> None:
        self._objects: list[WireframeObject] = []

    def build(self) -> list[WireframeObject]:
        """Assemble and return the full scene object list."""
        self._objects.clear()
        self._build_main_house_with_garage()
        self._build_driveway_and_path()
        self._build_streets()
        self._build_neighbor_houses()
        self._build_shops()
        self._build_trees()
        self._build_origin_axis_indicator()
        return list(self._objects)

    # -- Primitive helpers -------------------------------------------------

    def _add_box(
        self,
        center_x: float,
        base_y: float,
        center_z: float,
        width: float,
        height: float,
        depth: float,
        color: str,
    ) -> None:
        """Add an axis-aligned box with its bottom face at *base_y*."""
        half_width = width / 2
        half_depth = depth / 2

        bottom_vertices = [
            Vector3(center_x - half_width, base_y, center_z - half_depth),
            Vector3(center_x + half_width, base_y, center_z - half_depth),
            Vector3(center_x + half_width, base_y, center_z + half_depth),
            Vector3(center_x - half_width, base_y, center_z + half_depth),
        ]
        top_vertices = [
            Vector3(center_x - half_width, base_y + height, center_z - half_depth),
            Vector3(center_x + half_width, base_y + height, center_z - half_depth),
            Vector3(center_x + half_width, base_y + height, center_z + half_depth),
            Vector3(center_x - half_width, base_y + height, center_z + half_depth),
        ]
        vertices = bottom_vertices + top_vertices

        edges = [
            # Bottom face
            (0, 1),
            (1, 2),
            (2, 3),
            (3, 0),
            # Top face
            (4, 5),
            (5, 6),
            (6, 7),
            (7, 4),
            # Vertical pillars
            (0, 4),
            (1, 5),
            (2, 6),
            (3, 7),
        ]
        self._objects.append(WireframeObject(vertices, edges, color))

    def _add_prism_roof(
        self,
        center_x: float,
        base_y: float,
        center_z: float,
        width: float,
        peak_height: float,
        depth: float,
        color: str,
        ridge_axis: RidgeAxis = RidgeAxis.Z,
    ) -> None:
        """Add a triangular-prism roof whose ridge runs along *ridge_axis*."""
        half_width = width / 2
        half_depth = depth / 2

        base_vertices = [
            Vector3(center_x - half_width, base_y, center_z - half_depth),
            Vector3(center_x + half_width, base_y, center_z - half_depth),
            Vector3(center_x + half_width, base_y, center_z + half_depth),
            Vector3(center_x - half_width, base_y, center_z + half_depth),
        ]

        if ridge_axis == RidgeAxis.Z:
            ridge_vertices = [
                Vector3(center_x, base_y + peak_height, center_z - half_depth),
                Vector3(center_x, base_y + peak_height, center_z + half_depth),
            ]
            slope_edges = [(0, 4), (1, 4), (2, 5), (3, 5)]
        else:
            ridge_vertices = [
                Vector3(center_x - half_width, base_y + peak_height, center_z),
                Vector3(center_x + half_width, base_y + peak_height, center_z),
            ]
            slope_edges = [(0, 4), (3, 4), (1, 5), (2, 5)]

        vertices = base_vertices + ridge_vertices
        edges = [
            # Base rectangle
            (0, 1),
            (1, 2),
            (2, 3),
            (3, 0),
            # Slopes
            *slope_edges,
            # Ridge line
            (4, 5),
        ]
        self._objects.append(WireframeObject(vertices, edges, color))

    # -- Composite building helpers ----------------------------------------

    def _add_standard_house(
        self,
        position_x: float,
        position_z: float,
        wall_color: str = "saddlebrown",
        roof_color: str = "darkred",
    ) -> None:
        """Add a standard house with a door and two front windows."""
        # Walls
        self._add_box(position_x, 0, position_z, 5, 2.5, 5, wall_color)
        # Roof
        self._add_prism_roof(position_x, 2.5, position_z, 5.4, 1.3, 5.4, roof_color)
        # Front door
        front_face_z = position_z + 2.51
        self._add_box(position_x, 0, front_face_z, 1.0, 1.8, 0.1, "darkgreen")
        # Front windows (left and right of door)
        self._add_box(position_x - 1.25, 0.5, front_face_z, 1.0, 1.0, 0.1, "lightblue")
        self._add_box(position_x + 1.25, 0.5, front_face_z, 1.0, 1.0, 0.1, "lightblue")

    def _add_shop_building(
        self,
        position_x: float,
        position_z: float,
        wall_color: str = "firebrick",
    ) -> None:
        """Add a flat-roofed shop with a sign, display windows, and door."""
        wall_height = 3.0
        self._add_box(position_x, 0, position_z, 7, wall_height, 6, wall_color)
        # Flat roof cap
        self._add_box(position_x, wall_height, position_z, 7.4, 0.2, 6.4, "dimgray")
        # Storefront sign
        front_z = position_z + 3.0
        self._add_box(position_x, 3.5, front_z, 4, 0.8, 0.1, "wheat")
        # Display windows
        self._add_box(position_x - 2, 0.5, front_z + 0.01, 2.5, 2.0, 0.1, "cyan")
        self._add_box(position_x + 2, 0.5, front_z + 0.01, 2.5, 2.0, 0.1, "cyan")
        # Door
        self._add_box(position_x, 0, front_z + 0.01, 1.2, 2.2, 0.1, "black")

    def _add_tree(self, position_x: float, position_z: float) -> None:
        """Add a simple tree: brown trunk box + green triangular canopy."""
        self._add_box(position_x, 0, position_z, 0.5, 1.5, 0.5, "saddlebrown")
        self._add_prism_roof(
            position_x,
            1.5,
            position_z,
            2.5,
            3,
            2.5,
            "forestgreen",
            ridge_axis=RidgeAxis.Z,
        )

    # -- Scene composition -------------------------------------------------

    def _build_main_house_with_garage(self) -> None:
        """Main house, porch, chimney, and attached garage."""
        self._add_standard_house(0, 0)

        # Porch platform and support posts
        self._add_box(0, 0, 2.8, 2.0, 0.1, 1.5, "tan")
        self._add_box(-0.8, 0, 3.4, 0.2, 2.0, 0.2, "tan")
        self._add_box(0.8, 0, 3.4, 0.2, 2.0, 0.2, "tan")

        # Chimney
        self._add_box(1.5, 2.0, -1.5, 0.8, 2.5, 0.8, "gray")

        # Garage structure
        self._add_box(4.25, 0, 0, 3.5, 2.0, 4.5, "saddlebrown")
        self._add_prism_roof(4.25, 2.0, 0, 3.9, 1.0, 4.9, "darkred")
        self._add_box(4.25, 0, 2.26, 2.8, 1.8, 0.1, "white")  # Garage door

    def _build_driveway_and_path(self) -> None:
        """Driveway leading from garage and footpath to front door."""
        self._add_box(4.25, 0.02, 5.25, 3.0, 0, 5.5, "gray")
        self._add_box(0, 0.02, 5.0, 1.2, 0, 5.0, "lightgray")

    def _build_streets(self) -> None:
        """Main road, cross street, and center-line markings."""
        self._add_box(0, 0.01, 8, 100, 0, 4, "dimgray")  # Main street
        self._add_box(-20, 0.01, 8, 4, 0, 40, "dimgray")  # Cross street
        for stripe_index in range(-15, 16):
            stripe_x = stripe_index * 5
            self._add_box(stripe_x, 0.02, 8, 2, 0, 0.2, "yellow")

    def _build_neighbor_houses(self) -> None:
        """Row of neighboring houses across the street."""
        neighbor_configs = [
            (-15, "tan", "black"),
            (-7, "indianred", "maroon"),
            (15, "goldenrod", "chocolate"),
        ]
        for house_x, wall_color, roof_color in neighbor_configs:
            self._add_standard_house(house_x, 15, wall_color, roof_color)
            # Footpath from house to street
            self._add_box(house_x, 0.02, 11.5, 1.2, 0, 3, "lightgray")

    def _build_shops(self) -> None:
        """Commercial buildings along the cross street."""
        self._add_shop_building(-25, 8)
        self._add_shop_building(-33, 8)

    def _build_trees(self) -> None:
        """Scatter trees around the neighborhood."""
        tree_positions = [
            (-5, 5),
            (5, 5),
            (-12, 12),
            (12, 12),
            (-20, 10),
        ]
        for tree_x, tree_z in tree_positions:
            self._add_tree(tree_x, tree_z)

    def _build_origin_axis_indicator(self) -> None:
        """Small red marker at the world origin for debugging orientation."""
        self._add_box(0, 0, 0, 1, 0.1, 0.1, "red")


# ---------------------------------------------------------------------------
# Camera — holds view state and interpolation targets
# ---------------------------------------------------------------------------


@dataclass
class CameraState:
    """Current and target values for camera rotation, zoom, and offset."""

    rotation_x: float = DEFAULT_ROTATION_X
    rotation_y: float = DEFAULT_ROTATION_Y
    rotation_z: float = DEFAULT_ROTATION_Z
    zoom: float = DEFAULT_ZOOM
    offset_x: float = 0.0
    offset_y: float = 0.0

    target_rotation_x: float = DEFAULT_ROTATION_X
    target_rotation_y: float = DEFAULT_ROTATION_Y
    target_rotation_z: float = DEFAULT_ROTATION_Z
    target_zoom: float = DEFAULT_ZOOM
    target_offset_x: float = 0.0
    target_offset_y: float = 0.0

    def reset_to_defaults(self) -> None:
        """Smoothly return the camera to the default viewing angle."""
        self.target_rotation_x = DEFAULT_ROTATION_X
        self.target_rotation_y = DEFAULT_ROTATION_Y
        self.target_rotation_z = DEFAULT_ROTATION_Z
        self.target_zoom = DEFAULT_ZOOM
        self.target_offset_x = 0.0
        self.target_offset_y = 0.0

    def interpolate_toward_targets(self, blend: float = SMOOTHING_FACTOR) -> None:
        """Linearly interpolate current values toward their targets."""
        self.rotation_x += (self.target_rotation_x - self.rotation_x) * blend
        self.rotation_y += (self.target_rotation_y - self.rotation_y) * blend
        self.rotation_z += (self.target_rotation_z - self.rotation_z) * blend
        self.zoom += (self.target_zoom - self.zoom) * blend
        self.offset_x += (self.target_offset_x - self.offset_x) * blend
        self.offset_y += (self.target_offset_y - self.offset_y) * blend

    def transform_vertex(self, vertex: Vector3) -> Vector3:
        """Apply camera rotations and zoom to a world-space vertex."""
        rotated = vertex.rotated_around_x(self.rotation_x)
        rotated = rotated.rotated_around_y(self.rotation_y)
        rotated = rotated.rotated_around_z(self.rotation_z)
        return rotated.scaled(self.zoom)


# ---------------------------------------------------------------------------
# Input Handler — maps held keys to camera target adjustments
# ---------------------------------------------------------------------------


class InputHandler:
    """Translates continuous keyboard input into camera target changes."""

    def __init__(self, screen: turtle._Screen, camera: CameraState) -> None:
        self._screen = screen
        self._camera = camera
        self._held_keys: set[str] = set()

    def bind_all_controls(self, on_reset: callable, on_exit: callable) -> None:
        """Register key press/release bindings on the turtle screen."""
        self._screen.listen()

        # Continuous-hold keys
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
        for key in continuous_keys:
            self._screen.onkeypress(self._make_press_handler(key), key)
            self._screen.onkeyrelease(self._make_release_handler(key), key)

        # Single-press actions
        self._screen.onkey(on_reset, "r")
        self._screen.onkey(on_exit, "Escape")

    def apply_held_keys_to_camera(self) -> None:
        """Adjust camera targets based on whichever keys are currently held."""
        cam = self._camera

        # Rotation
        if "w" in self._held_keys:
            cam.target_rotation_x += ROTATION_SPEED
        if "s" in self._held_keys:
            cam.target_rotation_x -= ROTATION_SPEED
        if "d" in self._held_keys:
            cam.target_rotation_y += ROTATION_SPEED
        if "a" in self._held_keys:
            cam.target_rotation_y -= ROTATION_SPEED
        if "e" in self._held_keys:
            cam.target_rotation_z += ROTATION_SPEED
        if "q" in self._held_keys:
            cam.target_rotation_z -= ROTATION_SPEED

        # Zoom
        if "Up" in self._held_keys:
            cam.target_zoom = max(MIN_ZOOM, cam.target_zoom + ZOOM_SPEED)
        if "Down" in self._held_keys:
            cam.target_zoom = max(MIN_ZOOM, cam.target_zoom - ZOOM_SPEED)

        # Panning
        if "Right" in self._held_keys:
            cam.target_offset_x += PAN_SPEED
        if "Left" in self._held_keys:
            cam.target_offset_x -= PAN_SPEED
        if "Page_Up" in self._held_keys:
            cam.target_offset_y += PAN_SPEED
        if "Page_Down" in self._held_keys:
            cam.target_offset_y -= PAN_SPEED

    # -- Internal helpers --------------------------------------------------

    def _make_press_handler(self, key: str):
        return lambda: self._held_keys.add(key)

    def _make_release_handler(self, key: str):
        return lambda: self._held_keys.discard(key)


# ---------------------------------------------------------------------------
# Heads-Up Display — on-screen text overlay
# ---------------------------------------------------------------------------


class HeadsUpDisplay:
    """Renders control hints and camera telemetry on the turtle canvas."""

    def __init__(self, pen: turtle.Turtle) -> None:
        self._pen = pen

    def draw(self, camera: CameraState, object_count: int) -> None:
        """Write the full HUD to the screen."""
        self._draw_control_hints()
        self._draw_camera_telemetry(camera, object_count)

    # -- Private -----------------------------------------------------------

    def _write_at(
        self,
        x: float,
        y: float,
        text: str,
        font: tuple = HUD_FONT_BODY,
    ) -> None:
        self._pen.penup()
        self._pen.goto(x, y)
        self._pen.color("black")
        self._pen.write(text, font=font)

    def _draw_control_hints(self) -> None:
        left = HUD_LEFT_X
        y = HUD_TOP_Y
        self._write_at(left, y, "3D Rendered House", HUD_FONT_TITLE)
        y -= HUD_LINE_SPACING + 10
        self._write_at(
            left, y, "Movement Controls (Hold for continuous):", HUD_FONT_HEADING
        )
        hints = [
            "WASD: Rotate around X and Y axes",
            "QE: Rotate around Z axis",
            "Up/Down arrows: Zoom in/out",
            "Left/Right arrows: Pan left/right",
            "PgUp/PgDn: Pan up/down",
            "R: Reset view",
            "ESC: Exit",
        ]
        for line in hints:
            y -= HUD_LINE_SPACING
            self._write_at(left, y, line)

    def _draw_camera_telemetry(
        self,
        camera: CameraState,
        object_count: int,
    ) -> None:
        right = HUD_RIGHT_X
        y = HUD_TOP_Y
        self._write_at(right, y, "Camera Status:", HUD_FONT_HEADING)
        telemetry_lines = [
            f"Rotation X: {camera.rotation_x:.3f}",
            f"Rotation Y: {camera.rotation_y:.3f}",
            f"Rotation Z: {camera.rotation_z:.3f}",
            f"Zoom: {camera.zoom:.3f}",
            f"Objects: {object_count}",
        ]
        for line in telemetry_lines:
            y -= HUD_LINE_SPACING
            self._write_at(right, y, line)


# ---------------------------------------------------------------------------
# Renderer — orchestrates the frame loop
# ---------------------------------------------------------------------------


class SuburbanSceneRenderer:
    """Top-level renderer that ties scene, camera, input, and drawing together."""

    def __init__(self) -> None:
        # Turtle setup
        self._screen = turtle.Screen()
        self._screen.bgcolor(SCREEN_BACKGROUND_COLOR)
        self._screen.title(SCREEN_TITLE)
        self._screen.setup(SCREEN_WIDTH, SCREEN_HEIGHT)
        self._screen.tracer(0)

        self._pen = turtle.Turtle()
        self._pen.speed(0)
        self._pen.pensize(1)
        self._pen.hideturtle()

        # Core systems
        self._camera = CameraState()
        self._scene_objects = SuburbanSceneBuilder().build()
        self._hud = HeadsUpDisplay(self._pen)
        self._input_handler = InputHandler(self._screen, self._camera)
        self._input_handler.bind_all_controls(
            on_reset=self._camera.reset_to_defaults,
            on_exit=self._request_exit,
        )

        # Animation state
        self._is_running = True
        self._previous_frame_time = time.time()

    # -- Public entry point ------------------------------------------------

    def run(self) -> None:
        """Start the main rendering loop (blocks until exit)."""
        while self._is_running:
            current_time = time.time()
            elapsed = current_time - self._previous_frame_time

            if elapsed >= TARGET_FRAME_INTERVAL:
                self._render_single_frame()
                self._previous_frame_time = current_time
            else:
                time.sleep(IDLE_SLEEP_SECONDS)

        self._screen.bye()

    # -- Frame pipeline ----------------------------------------------------

    def _render_single_frame(self) -> None:
        """Process input, update camera, draw scene, and refresh."""
        self._input_handler.apply_held_keys_to_camera()
        self._camera.interpolate_toward_targets()
        self._pen.clear()
        self._draw_all_objects()
        self._hud.draw(self._camera, len(self._scene_objects))
        self._screen.update()

    def _draw_all_objects(self) -> None:
        """Depth-sort scene objects and draw back-to-front."""
        # Compute average transformed Z for each object
        depth_sorted_objects = sorted(
            self._scene_objects,
            key=lambda obj: self._average_depth(obj),
            reverse=True,
        )

        for wireframe_object in depth_sorted_objects:
            for start_index, end_index in wireframe_object.edges:
                if start_index < len(wireframe_object.vertices) and end_index < len(
                    wireframe_object.vertices
                ):
                    self._draw_edge_3d(
                        wireframe_object.vertices[start_index],
                        wireframe_object.vertices[end_index],
                        wireframe_object.color,
                    )

    def _average_depth(self, wireframe_object: WireframeObject) -> float:
        """Return the mean Z of all transformed vertices (for depth sorting)."""
        total_z = sum(
            self._camera.transform_vertex(vertex).z
            for vertex in wireframe_object.vertices
        )
        return total_z / len(wireframe_object.vertices)

    def _draw_edge_3d(
        self,
        vertex_a: Vector3,
        vertex_b: Vector3,
        color: str,
    ) -> None:
        """Transform, project, and draw a single 3D edge to the screen."""
        transformed_a = self._camera.transform_vertex(vertex_a)
        transformed_b = self._camera.transform_vertex(vertex_b)

        screen_a = transformed_a.project_to_screen()
        screen_b = transformed_b.project_to_screen()

        # Cull edges that project far outside the visible area
        if (
            abs(screen_a.x) > OFF_SCREEN_THRESHOLD
            or abs(screen_a.y) > OFF_SCREEN_THRESHOLD
            or abs(screen_b.x) > OFF_SCREEN_THRESHOLD
            or abs(screen_b.y) > OFF_SCREEN_THRESHOLD
        ):
            return

        # Apply camera pan offset
        final_x1 = screen_a.x + self._camera.offset_x
        final_y1 = screen_a.y + self._camera.offset_y
        final_x2 = screen_b.x + self._camera.offset_x
        final_y2 = screen_b.y + self._camera.offset_y

        try:
            self._pen.color(color)
            self._pen.penup()
            self._pen.goto(final_x1, final_y1)
            self._pen.pendown()
            self._pen.goto(final_x2, final_y2)
        except turtle.Terminator:
            pass  # Window closed mid-draw; ignore gracefully

    # -- Callbacks ---------------------------------------------------------

    def _request_exit(self) -> None:
        self._is_running = False


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------


def main() -> None:
    """Print usage instructions and launch the interactive renderer."""
    instructions = [
        "Starting 3D Suburban Scene Renderer (High-Level)...",
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

    renderer = SuburbanSceneRenderer()
    renderer.run()


if __name__ == "__main__":
    main()
