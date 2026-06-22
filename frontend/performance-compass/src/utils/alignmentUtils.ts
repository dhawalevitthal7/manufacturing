/**
 * Alignment Utilities
 * ===================
 * OKR alignment calculations and analysis
 */

import {
  ConstellationNode,
  ConstellationEdge,
  ExecutiveInsight,
  AlignmentType,
} from '@/types/constellation.types';

/**
 * Calculate alignment score for a node
 */
export const calculateAlignmentScore = (
  node: ConstellationNode,
  incomingEdges: ConstellationEdge[],
  nodes: ConstellationNode[]
): number => {
  if (!incomingEdges.length) {
    return 0;
  }

  const parentNodes = incomingEdges.map((edge) =>
    nodes.find((n) => n.id === edge.source)
  ).filter(Boolean) as ConstellationNode[];

  if (!parentNodes.length) {
    return 0;
  }

  const totalWeight = incomingEdges.reduce((sum, edge) => sum + edge.contribution_weight, 0);
  const weightedScore = incomingEdges.reduce(
    (sum, edge) => sum + edge.contribution_score * (edge.contribution_weight / 5),
    0
  );

  return weightedScore / (incomingEdges.length || 1);
};

/**
 * Find orphaned OKRs (no incoming alignment edges)
 */
export const findOrphanedOKRs = (
  nodes: ConstellationNode[],
  edges: ConstellationEdge[]
): ConstellationNode[] => {
  const targetIds = new Set(edges.map((e) => e.target));

  return nodes.filter((node) => {
    // Organization level can never be orphaned
    if (node.level === 'organization') return false;
    return !targetIds.has(node.id) && !node.is_orphaned;
  });
};

/**
 * Detect broken/weak alignment connections
 */
export const findBrokenAlignments = (
  edges: ConstellationEdge[],
  weakThreshold: number = 40
): ConstellationEdge[] => {
  return edges.filter((edge) => edge.contribution_score < weakThreshold || edge.is_broken);
};

/**
 * Find bottleneck nodes (many dependents, low alignment)
 */
export const findBottlenecks = (
  nodes: ConstellationNode[],
  edges: ConstellationEdge[],
  minChildren: number = 3
): ConstellationNode[] => {
  return nodes.filter((node) => {
    const children = edges.filter((e) => e.source === node.id);
    const avgAlignment = children.length
      ? children.reduce((sum, e) => sum + e.contribution_score, 0) / children.length
      : 100;

    return children.length >= minChildren && (avgAlignment < 60 || node.alignment_health !== 'healthy');
  });
};

/**
 * Find strong contributors (aligned and progressing well)
 */
export const findStrongContributors = (
  nodes: ConstellationNode[],
  edges: ConstellationEdge[],
  minParents: number = 1
): ConstellationNode[] => {
  return nodes.filter((node) => {
    const parents = edges.filter((e) => e.target === node.id);
    const avgAlignment = parents.length
      ? parents.reduce((sum, e) => sum + e.contribution_score, 0) / parents.length
      : 0;

    return (
      parents.length >= minParents &&
      avgAlignment > 75 &&
      node.progress > 70 &&
      node.alignment_health === 'healthy'
    );
  });
};

/**
 * Calculate alignment health for OKR network
 */
export const calculateNetworkAlignmentHealth = (
  nodes: ConstellationNode[],
  edges: ConstellationEdge[]
): { score: number; strength: 'strong' | 'moderate' | 'weak' | 'critical' } => {
  if (!nodes.length || !edges.length) {
    return { score: 0, strength: 'critical' };
  }

  const avgScore = edges.reduce((sum, e) => sum + e.contribution_score, 0) / edges.length;
  const orphanCount = findOrphanedOKRs(nodes, edges).length;
  const brokenCount = findBrokenAlignments(edges).length;
  const orphanPenalty = (orphanCount / nodes.length) * 20;
  const brokenPenalty = (brokenCount / edges.length) * 15;

  const score = Math.max(0, avgScore - orphanPenalty - brokenPenalty);

  let strength: 'strong' | 'moderate' | 'weak' | 'critical';
  if (score >= 75) strength = 'strong';
  else if (score >= 60) strength = 'moderate';
  else if (score >= 40) strength = 'weak';
  else strength = 'critical';

  return { score: Math.round(score), strength };
};

/**
 * Detect risk propagation paths
 */
export const findRiskPropagationPaths = (
  nodes: ConstellationNode[],
  edges: ConstellationEdge[],
  riskNodeId: string,
  maxDepth: number = 3
): ConstellationNode[][] => {
  const riskNode = nodes.find((n) => n.id === riskNodeId);
  if (!riskNode) return [];

  const paths: ConstellationNode[][] = [];

  const dfs = (nodeId: string, path: ConstellationNode[], depth: number) => {
    if (depth > maxDepth) return;

    const parents = edges
      .filter((e) => e.target === nodeId)
      .map((e) => nodes.find((n) => n.id === e.source))
      .filter(Boolean) as ConstellationNode[];

    parents.forEach((parent) => {
      const newPath = [...path, parent];
      paths.push(newPath);
      dfs(parent.id, newPath, depth + 1);
    });
  };

  dfs(riskNodeId, [riskNode], 0);
  return paths;
};

/**
 * Calculate alignment impact (how much one node affects others)
 */
export const calculateAlignmentImpact = (
  nodeId: string,
  edges: ConstellationEdge[]
): number => {
  const outgoing = edges.filter((e) => e.source === nodeId);
  if (!outgoing.length) return 0;

  const avgWeight = outgoing.reduce((sum, e) => sum + e.contribution_weight, 0) / outgoing.length;
  const avgScore = outgoing.reduce((sum, e) => sum + e.contribution_score, 0) / outgoing.length;

  // Impact = number of dependents * average alignment quality
  return (outgoing.length * avgWeight * avgScore) / 500;
};

/**
 * Find critical cross-functional dependencies
 */
export const findCrossFunctionalDependencies = (
  nodes: ConstellationNode[],
  edges: ConstellationEdge[]
): ConstellationEdge[] => {
  return edges.filter((edge) => {
    const source = nodes.find((n) => n.id === edge.source);
    const target = nodes.find((n) => n.id === edge.target);

    if (!source || !target) return false;

    // Different departments/plants = cross-functional
    const differentDept =
      source.department !== target.department && source.department && target.department;
    const differentPlant = source.plant !== target.plant && source.plant && target.plant;

    return (differentDept || differentPlant) && edge.alignment_type === 'cross-functional';
  });
};

/**
 * Generate executive insights from alignment data
 */
export const generateAlignmentInsights = (
  nodes: ConstellationNode[],
  edges: ConstellationEdge[]
): ExecutiveInsight[] => {
  const insights: ExecutiveInsight[] = [];

  // Orphaned OKRs
  const orphans = findOrphanedOKRs(nodes, edges);
  if (orphans.length > 0) {
    insights.push({
      id: 'orphan-okrs',
      type: 'orphan',
      severity: orphans.length > 5 ? 'critical' : 'high',
      title: `${orphans.length} Orphaned OKRs Found`,
      description: `${orphans.length} OKRs have no alignment to higher-level objectives. These may represent tactical work rather than strategic alignment.`,
      affectedNodes: orphans.map((o) => o.id),
      actionable: true,
      actionText: 'Review & Align',
    });
  }

  // Bottlenecks
  const bottlenecks = findBottlenecks(nodes, edges);
  if (bottlenecks.length > 0) {
    const topBottleneck = bottlenecks[0];
    insights.push({
      id: 'bottleneck-risk',
      type: 'bottleneck',
      severity: 'high',
      title: 'Critical Bottleneck Detected',
      description: `${topBottleneck.objective} in ${topBottleneck.department || topBottleneck.plant || 'organization'} is blocking progress for multiple dependent OKRs.`,
      affectedNodes: [topBottleneck.id],
      impact:
        edges.filter((e) => e.source === topBottleneck.id).length *
        (topBottleneck.confidence_score / 100),
      actionable: true,
      actionText: 'Escalate',
    });
  }

  // Weak alignment
  const weakAlignments = findBrokenAlignments(edges, 50);
  if (weakAlignments.length > edges.length * 0.2) {
    insights.push({
      id: 'weak-alignment',
      type: 'weak_alignment',
      severity: 'medium',
      title: 'Low Alignment Quality Detected',
      description: `${weakAlignments.length} alignment connections have scores below 50%. Consider reviewing strategic coherence.`,
      impact: (weakAlignments.length / edges.length) * 100,
      actionable: true,
      actionText: 'Review Alignments',
    });
  }

  // Risk propagation
  const criticalNodes = nodes.filter((n) => n.risk_level === 'critical');
  if (criticalNodes.length > 0) {
    const riskPaths = findRiskPropagationPaths(nodes, edges, criticalNodes[0].id, 2);
    if (riskPaths.length > 0) {
      insights.push({
        id: 'risk-propagation',
        type: 'risk_propagation',
        severity: 'critical',
        title: 'Risk Propagation Chain Detected',
        description: `Critical risk in ${criticalNodes[0].objective} could propagate to ${riskPaths.length} upstream OKRs.`,
        affectedNodes: riskPaths.flat().map((n) => n.id),
        actionable: true,
        actionText: 'Mitigate',
      });
    }
  }

  // Top aligned performers
  const strongContributors = findStrongContributors(nodes, edges, 2);
  if (strongContributors.length > 0) {
    insights.push({
      id: 'top-aligned',
      type: 'strong_contributor',
      severity: 'low',
      title: `${strongContributors.length} Strong Contributors`,
      description: `These OKRs show excellent alignment and progress. Consider them as models for organizational alignment strategy.`,
      affectedNodes: strongContributors.map((n) => n.id),
    });
  }

  return insights;
};

export const alignmentUtils = {
  calculateAlignmentScore,
  findOrphanedOKRs,
  findBrokenAlignments,
  findBottlenecks,
  findStrongContributors,
  calculateNetworkAlignmentHealth,
  findRiskPropagationPaths,
  calculateAlignmentImpact,
  findCrossFunctionalDependencies,
  generateAlignmentInsights,
};
