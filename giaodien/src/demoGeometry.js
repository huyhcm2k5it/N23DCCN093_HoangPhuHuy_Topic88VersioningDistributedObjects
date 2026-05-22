export function createPyramidDemoGeometry(material = 'baseline_steel') {
  return {
    type: 'Polygon',
    vertices: [
      { x: 0, y: 0, z: 0 },
      { x: 120, y: 0, z: 0 },
      { x: 0, y: 80, z: 0 },
      { x: 30, y: 30, z: 60 },
    ],
    edges: [[0, 1], [1, 2], [2, 0], [0, 3], [1, 3], [2, 3]],
    faces: [[0, 1, 2], [0, 1, 3], [1, 2, 3], [2, 0, 3]],
    properties: {
      category: 'engine',
      material,
      tolerance: 0.01,
      tolerance_mm: 0.01,
      weight_kg: 18.5,
    },
  };
}

export function createTriangleDemoGeometry(material = 'network_demo_alloy') {
  return {
    type: 'Polygon',
    vertices: [
      { x: 0, y: 0, z: 0 },
      { x: 1, y: 0, z: 0 },
      { x: 0, y: 1, z: 0 },
    ],
    edges: [[0, 1], [1, 2], [2, 0]],
    faces: [[0, 1, 2]],
    properties: {
      category: 'engine',
      material,
      tolerance: 0.01,
      tolerance_mm: 0.01,
      weight_kg: 1.0,
    },
  };
}
