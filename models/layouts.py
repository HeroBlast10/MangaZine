"""
MangaZine Layout Templates
CSS Grid configurations for variable panel layouts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from models.schemas import LayoutTemplate


@dataclass
class LayoutConfig:
    """Configuration for a single layout template."""
    
    panel_count: int
    grid_template_columns: str
    grid_template_rows: str
    grid_template_areas: str
    panel_areas: List[str]
    description: str


LAYOUT_CONFIGS: Dict[LayoutTemplate, LayoutConfig] = {
    # 1 panel layouts (splash pages)
    LayoutTemplate.SPLASH_FULL: LayoutConfig(
        panel_count=1,
        grid_template_columns="1fr",
        grid_template_rows="1fr",
        grid_template_areas='"p1"',
        panel_areas=["p1"],
        description="Full page splash panel",
    ),
    
    # 2 panel layouts
    LayoutTemplate.PANELS_2_VERTICAL: LayoutConfig(
        panel_count=2,
        grid_template_columns="1fr",
        grid_template_rows="1fr 1fr",
        grid_template_areas='"p1" "p2"',
        panel_areas=["p1", "p2"],
        description="Two panels stacked vertically",
    ),
    LayoutTemplate.PANELS_2_HORIZONTAL: LayoutConfig(
        panel_count=2,
        grid_template_columns="1fr 1fr",
        grid_template_rows="1fr",
        grid_template_areas='"p1 p2"',
        panel_areas=["p1", "p2"],
        description="Two panels side by side",
    ),
    
    # 3 panel layouts
    LayoutTemplate.PANELS_3_VERTICAL: LayoutConfig(
        panel_count=3,
        grid_template_columns="1fr",
        grid_template_rows="1fr 1fr 1fr",
        grid_template_areas='"p1" "p2" "p3"',
        panel_areas=["p1", "p2", "p3"],
        description="Three panels stacked vertically",
    ),
    LayoutTemplate.PANELS_3_TOP_SPLIT: LayoutConfig(
        panel_count=3,
        grid_template_columns="1fr 1fr",
        grid_template_rows="1fr 1fr",
        grid_template_areas='"p1 p2" "p3 p3"',
        panel_areas=["p1", "p2", "p3"],
        description="Two small panels on top, one wide panel on bottom",
    ),
    LayoutTemplate.PANELS_3_BOTTOM_SPLIT: LayoutConfig(
        panel_count=3,
        grid_template_columns="1fr 1fr",
        grid_template_rows="1fr 1fr",
        grid_template_areas='"p1 p1" "p2 p3"',
        panel_areas=["p1", "p2", "p3"],
        description="One wide panel on top, two small panels on bottom",
    ),
    
    # 4 panel layouts
    LayoutTemplate.PANELS_4_GRID: LayoutConfig(
        panel_count=4,
        grid_template_columns="1fr 1fr",
        grid_template_rows="1fr 1fr",
        grid_template_areas='"p1 p2" "p3 p4"',
        panel_areas=["p1", "p2", "p3", "p4"],
        description="Classic 2x2 grid layout",
    ),
    LayoutTemplate.PANELS_4_VERTICAL: LayoutConfig(
        panel_count=4,
        grid_template_columns="1fr",
        grid_template_rows="1fr 1fr 1fr 1fr",
        grid_template_areas='"p1" "p2" "p3" "p4"',
        panel_areas=["p1", "p2", "p3", "p4"],
        description="Four panels stacked vertically",
    ),
    LayoutTemplate.PANELS_4_L_SHAPE: LayoutConfig(
        panel_count=4,
        grid_template_columns="1fr 1fr",
        grid_template_rows="1fr 1fr 1fr",
        grid_template_areas='"p1 p1" "p2 p3" "p2 p4"',
        panel_areas=["p1", "p2", "p3", "p4"],
        description="L-shaped layout with one tall panel",
    ),
    
    # 5 panel layouts
    LayoutTemplate.PANELS_5_CROSS: LayoutConfig(
        panel_count=5,
        grid_template_columns="1fr 1fr 1fr",
        grid_template_rows="1fr 1fr 1fr",
        grid_template_areas='"p1 p2 p2" "p3 p3 p4" "p3 p3 p5"',
        panel_areas=["p1", "p2", "p3", "p4", "p5"],
        description="Cross pattern with center emphasis",
    ),
    LayoutTemplate.PANELS_5_T_SHAPE: LayoutConfig(
        panel_count=5,
        grid_template_columns="1fr 1fr 1fr",
        grid_template_rows="1fr 1fr 1fr",
        grid_template_areas='"p1 p1 p1" "p2 p3 p4" "p5 p5 p5"',
        panel_areas=["p1", "p2", "p3", "p4", "p5"],
        description="T-shaped layout",
    ),
    LayoutTemplate.PANELS_5_STAGGERED: LayoutConfig(
        panel_count=5,
        grid_template_columns="1fr 1fr",
        grid_template_rows="1fr 1fr 1fr",
        grid_template_areas='"p1 p2" "p3 p3" "p4 p5"',
        panel_areas=["p1", "p2", "p3", "p4", "p5"],
        description="Staggered layout with wide center",
    ),
    
    # 6 panel layouts
    LayoutTemplate.PANELS_6_GRID: LayoutConfig(
        panel_count=6,
        grid_template_columns="1fr 1fr",
        grid_template_rows="1fr 1fr 1fr",
        grid_template_areas='"p1 p2" "p3 p4" "p5 p6"',
        panel_areas=["p1", "p2", "p3", "p4", "p5", "p6"],
        description="Classic 2x3 grid layout",
    ),
    LayoutTemplate.PANELS_6_DYNAMIC: LayoutConfig(
        panel_count=6,
        grid_template_columns="1fr 1fr 1fr",
        grid_template_rows="1fr 1fr 1fr",
        grid_template_areas='"p1 p1 p2" "p3 p4 p4" "p5 p5 p6"',
        panel_areas=["p1", "p2", "p3", "p4", "p5", "p6"],
        description="Dynamic layout with varying panel sizes",
    ),
    
    # 7 panel layouts
    LayoutTemplate.PANELS_7_COMPLEX: LayoutConfig(
        panel_count=7,
        grid_template_columns="1fr 1fr 1fr",
        grid_template_rows="1fr 1fr 1fr",
        grid_template_areas='"p1 p2 p3" "p4 p4 p5" "p6 p7 p7"',
        panel_areas=["p1", "p2", "p3", "p4", "p5", "p6", "p7"],
        description="Complex 7-panel layout",
    ),
    
    # 8 panel layouts
    LayoutTemplate.PANELS_8_GRID: LayoutConfig(
        panel_count=8,
        grid_template_columns="1fr 1fr",
        grid_template_rows="1fr 1fr 1fr 1fr",
        grid_template_areas='"p1 p2" "p3 p4" "p5 p6" "p7 p8"',
        panel_areas=["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8"],
        description="Dense 2x4 grid layout",
    ),
}


def get_layout_config(template: LayoutTemplate) -> LayoutConfig:
    """Get the CSS grid configuration for a layout template."""
    return LAYOUT_CONFIGS[template]


def get_panel_count(template: LayoutTemplate) -> int:
    """Get the number of panels for a layout template."""
    return LAYOUT_CONFIGS[template].panel_count


def get_templates_for_panel_count(count: int) -> List[LayoutTemplate]:
    """Get all layout templates that support a specific panel count."""
    return [
        template for template, config in LAYOUT_CONFIGS.items()
        if config.panel_count == count
    ]


def suggest_layout_for_scene(
    scene_type: str,
    panel_count: int,
    is_action: bool = False,
    is_climax: bool = False,
) -> LayoutTemplate:
    """
    Suggest an appropriate layout template based on scene characteristics.
    
    Parameters
    ----------
    scene_type : str
        Type of scene (e.g., "dialogue", "action", "establishing")
    panel_count : int
        Desired number of panels
    is_action : bool
        Whether the scene is action-heavy
    is_climax : bool
        Whether this is a climactic moment
    
    Returns
    -------
    LayoutTemplate
        Suggested layout template
    """
    templates = get_templates_for_panel_count(panel_count)
    
    if not templates:
        # Fallback to closest available
        if panel_count <= 1:
            return LayoutTemplate.SPLASH_FULL
        elif panel_count <= 4:
            return LayoutTemplate.PANELS_4_GRID
        else:
            return LayoutTemplate.PANELS_6_GRID
    
    # For climax scenes, prefer splash or dynamic layouts
    if is_climax and panel_count == 1:
        return LayoutTemplate.SPLASH_FULL
    
    # For action scenes, prefer dynamic/asymmetric layouts
    if is_action:
        dynamic_templates = [t for t in templates if "dynamic" in t.value or "l_shape" in t.value or "cross" in t.value]
        if dynamic_templates:
            return dynamic_templates[0]
    
    # Default to first available template
    return templates[0]
