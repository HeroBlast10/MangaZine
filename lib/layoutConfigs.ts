/**
 * MangaZine Layout Configurations
 * CSS Grid configurations for variable panel layouts.
 */

export interface LayoutConfig {
  panelCount: number;
  gridTemplateColumns: string;
  gridTemplateRows: string;
  gridTemplateAreas: string;
  panelAreas: string[];
  description: string;
}

export const LAYOUT_CONFIGS: Record<string, LayoutConfig> = {
  // 1 panel layouts (splash pages)
  splash_full: {
    panelCount: 1,
    gridTemplateColumns: '1fr',
    gridTemplateRows: '1fr',
    gridTemplateAreas: '"p1"',
    panelAreas: ['p1'],
    description: 'Full page splash panel',
  },

  // 2 panel layouts
  panels_2_vertical: {
    panelCount: 2,
    gridTemplateColumns: '1fr',
    gridTemplateRows: '1fr 1fr',
    gridTemplateAreas: '"p1" "p2"',
    panelAreas: ['p1', 'p2'],
    description: 'Two panels stacked vertically',
  },
  panels_2_horizontal: {
    panelCount: 2,
    gridTemplateColumns: '1fr 1fr',
    gridTemplateRows: '1fr',
    gridTemplateAreas: '"p1 p2"',
    panelAreas: ['p1', 'p2'],
    description: 'Two panels side by side',
  },

  // 3 panel layouts
  panels_3_vertical: {
    panelCount: 3,
    gridTemplateColumns: '1fr',
    gridTemplateRows: '1fr 1fr 1fr',
    gridTemplateAreas: '"p1" "p2" "p3"',
    panelAreas: ['p1', 'p2', 'p3'],
    description: 'Three panels stacked vertically',
  },
  panels_3_top_split: {
    panelCount: 3,
    gridTemplateColumns: '1fr 1fr',
    gridTemplateRows: '1fr 1fr',
    gridTemplateAreas: '"p1 p2" "p3 p3"',
    panelAreas: ['p1', 'p2', 'p3'],
    description: 'Two small panels on top, one wide panel on bottom',
  },
  panels_3_bottom_split: {
    panelCount: 3,
    gridTemplateColumns: '1fr 1fr',
    gridTemplateRows: '1fr 1fr',
    gridTemplateAreas: '"p1 p1" "p2 p3"',
    panelAreas: ['p1', 'p2', 'p3'],
    description: 'One wide panel on top, two small panels on bottom',
  },

  // 4 panel layouts
  panels_4_grid: {
    panelCount: 4,
    gridTemplateColumns: '1fr 1fr',
    gridTemplateRows: '1fr 1fr',
    gridTemplateAreas: '"p1 p2" "p3 p4"',
    panelAreas: ['p1', 'p2', 'p3', 'p4'],
    description: 'Classic 2x2 grid layout',
  },
  panels_4_vertical: {
    panelCount: 4,
    gridTemplateColumns: '1fr',
    gridTemplateRows: '1fr 1fr 1fr 1fr',
    gridTemplateAreas: '"p1" "p2" "p3" "p4"',
    panelAreas: ['p1', 'p2', 'p3', 'p4'],
    description: 'Four panels stacked vertically',
  },
  panels_4_l_shape: {
    panelCount: 4,
    gridTemplateColumns: '1fr 1fr',
    gridTemplateRows: '1fr 1fr 1fr',
    gridTemplateAreas: '"p1 p1" "p2 p3" "p2 p4"',
    panelAreas: ['p1', 'p2', 'p3', 'p4'],
    description: 'L-shaped layout with one tall panel',
  },

  // 5 panel layouts
  panels_5_cross: {
    panelCount: 5,
    gridTemplateColumns: '1fr 1fr 1fr',
    gridTemplateRows: '1fr 1fr 1fr',
    gridTemplateAreas: '"p1 p2 p2" "p3 p3 p4" "p3 p3 p5"',
    panelAreas: ['p1', 'p2', 'p3', 'p4', 'p5'],
    description: 'Cross pattern with center emphasis',
  },
  panels_5_t_shape: {
    panelCount: 5,
    gridTemplateColumns: '1fr 1fr 1fr',
    gridTemplateRows: '1fr 1fr 1fr',
    gridTemplateAreas: '"p1 p1 p1" "p2 p3 p4" "p5 p5 p5"',
    panelAreas: ['p1', 'p2', 'p3', 'p4', 'p5'],
    description: 'T-shaped layout',
  },
  panels_5_staggered: {
    panelCount: 5,
    gridTemplateColumns: '1fr 1fr',
    gridTemplateRows: '1fr 1fr 1fr',
    gridTemplateAreas: '"p1 p2" "p3 p3" "p4 p5"',
    panelAreas: ['p1', 'p2', 'p3', 'p4', 'p5'],
    description: 'Staggered layout with wide center',
  },

  // 6 panel layouts
  panels_6_grid: {
    panelCount: 6,
    gridTemplateColumns: '1fr 1fr',
    gridTemplateRows: '1fr 1fr 1fr',
    gridTemplateAreas: '"p1 p2" "p3 p4" "p5 p6"',
    panelAreas: ['p1', 'p2', 'p3', 'p4', 'p5', 'p6'],
    description: 'Classic 2x3 grid layout',
  },
  panels_6_dynamic: {
    panelCount: 6,
    gridTemplateColumns: '1fr 1fr 1fr',
    gridTemplateRows: '1fr 1fr 1fr',
    gridTemplateAreas: '"p1 p1 p2" "p3 p4 p4" "p5 p5 p6"',
    panelAreas: ['p1', 'p2', 'p3', 'p4', 'p5', 'p6'],
    description: 'Dynamic layout with varying panel sizes',
  },

  // 7 panel layouts
  panels_7_complex: {
    panelCount: 7,
    gridTemplateColumns: '1fr 1fr 1fr',
    gridTemplateRows: '1fr 1fr 1fr',
    gridTemplateAreas: '"p1 p2 p3" "p4 p4 p5" "p6 p7 p7"',
    panelAreas: ['p1', 'p2', 'p3', 'p4', 'p5', 'p6', 'p7'],
    description: 'Complex 7-panel layout',
  },

  // 8 panel layouts
  panels_8_grid: {
    panelCount: 8,
    gridTemplateColumns: '1fr 1fr',
    gridTemplateRows: '1fr 1fr 1fr 1fr',
    gridTemplateAreas: '"p1 p2" "p3 p4" "p5 p6" "p7 p8"',
    panelAreas: ['p1', 'p2', 'p3', 'p4', 'p5', 'p6', 'p7', 'p8'],
    description: 'Dense 2x4 grid layout',
  },
};

export function getLayoutConfig(template: string): LayoutConfig {
  return LAYOUT_CONFIGS[template] || LAYOUT_CONFIGS['panels_4_grid'];
}

export function getPanelCount(template: string): number {
  return getLayoutConfig(template).panelCount;
}
