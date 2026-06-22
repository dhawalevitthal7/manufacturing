/**
 * Graph Layout Utilities
 * ======================
 * Force-directed layout and positioning algorithms
 * OPTIMIZED: Reduced warmup ticks & faster convergence for low-latency rendering
 */

export interface ForceGraphConfig {
  nodeStrength?: number;
  linkStrength?: number;
  linkDistance?: (link: any) => number;
  chargeStrength?: (node: any) => number;
  centerStrength?: number;
  collideRadius?: (node: any) => number;
  velocityDecay?: number;
  alphaDecay?: number;
  alphaMin?: number;
  alphaTarget?: number;
  warmupTicks?: number;
  cooldownTicks?: number;
}

export const getForceGraphConfig = (nodeCount: number): ForceGraphConfig => {
  // Adaptive configuration based on node count
  const scale = Math.min(1, 500 / Math.max(1, nodeCount));

  // For small graphs (<30 nodes), minimal warmup; larger graphs get slightly more
  const warmup = nodeCount < 30 ? 10 : nodeCount < 100 ? 20 : 30;
  // Cap cooldown to prevent long simulation
  const cooldown = nodeCount < 50 ? 100 : 200;

  return {
    nodeStrength: -50 * scale,
    linkStrength: 0.5,
    linkDistance: (link: any) => {
      // Stronger connections = shorter distance
      return 80 - (link.contribution_weight || 1) * 10;
    },
    chargeStrength: (node: any) => {
      // Larger nodes = stronger repulsion
      const sizeMap: Record<string, number> = {
        organization: 200,
        ORGANIZATION: 200,
        region: 150,
        REGION: 150,
        plant: 120,
        PLANT: 120,
        department: 80,
        DEPARTMENT: 80,
        team: 50,
        TEAM: 50,
        employee: 30,
        EMPLOYEE: 30,
      };
      return -(sizeMap[node.level] || 50) * scale;
    },
    centerStrength: 0.05,
    collideRadius: (node: any) => {
      return (node.displaySize || 20) + 5;
    },
    velocityDecay: 0.5,        // Was 0.4 — higher = faster settling
    alphaDecay: 0.05,           // Was 0.02 — higher = faster convergence
    alphaMin: 0.005,            // Was 0.001 — stop sooner
    alphaTarget: 0,
    warmupTicks: warmup,        // Was 50 — reduced significantly
    cooldownTicks: cooldown,    // Added — caps simulation time
  };
};

/**
 * Calculate orbital positions for organization structure
 * Places nodes in orbital rings based on hierarchy level
 */
export const getOrbitalPosition = (
  node: any,
  centerX: number,
  centerY: number,
  angle: number
): { x: number; y: number } => {
  const orbitalRadii: Record<string, number> = {
    organization: 0,
    ORGANIZATION: 0,
    region: 150,
    REGION: 150,
    plant: 280,
    PLANT: 280,
    department: 400,
    DEPARTMENT: 400,
    team: 500,
    TEAM: 500,
    employee: 580,
    EMPLOYEE: 580,
  };

  const radius = orbitalRadii[node.level] || 300;
  const x = centerX + radius * Math.cos(angle);
  const y = centerY + radius * Math.sin(angle);

  return { x, y };
};

/**
 * Calculate cluster positions
 * Groups nodes by scope (plant, department, etc.)
 */
export const getClusterCenter = (
  nodes: any[],
  clusterKey: string
): { x: number; y: number } => {
  if (nodes.length === 0) return { x: 0, y: 0 };

  const xs = nodes.map((n) => n.x || 0);
  const ys = nodes.map((n) => n.y || 0);

  return {
    x: xs.reduce((a, b) => a + b) / xs.length,
    y: ys.reduce((a, b) => a + b) / ys.length,
  };
};

/**
 * Cooldown simulation - gradually stabilize graph
 */
export const getCooldownFunction = () => {
  let tick = 0;
  const maxTicks = 200; // Was 300 — faster cooldown

  return () => {
    tick++;
    return Math.max(0, 1 - tick / maxTicks);
  };
};

export const graphLayoutUtils = {
  getForceGraphConfig,
  getOrbitalPosition,
  getClusterCenter,
  getCooldownFunction,
};
