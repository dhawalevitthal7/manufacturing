/**
 * Constellation API Client
 * =======================
 * API methods for fetching and managing constellation data
 */

import {
  ConstellationAPIResponse,
  ConstellationFilters,
  ConstellationNode,
} from '@/types/constellation.types';

function normalizeNodeLevel(level: string): ConstellationNode['level'] {
  const l = (level || '').toLowerCase();
  if (l === 'individual') return 'employee';
  if (
    l === 'organization' ||
    l === 'region' ||
    l === 'plant' ||
    l === 'department' ||
    l === 'team'
  ) {
    return l;
  }
  return 'employee';
}

function normalizeConstellationResponse(
  data: ConstellationAPIResponse,
): ConstellationAPIResponse {
  return {
    ...data,
    nodes: data.nodes.map((n) => ({
      ...n,
      level: normalizeNodeLevel(n.level),
    })),
  };
}
import { useAuthStore } from '@/lib/stores/auth-store';
import { levelsToApiParam } from '@/utils/constellationFilterUtils';

const BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

/**
 * Get auth headers with token
 */
function getAuthHeaders(): HeadersInit {
  const token = useAuthStore.getState().getToken();
  return {
    'Content-Type': 'application/json',
    ...(token && { 'Authorization': `Bearer ${token}` }),
  };
}

/**
 * Fetch constellation data from backend
 */
export const getConstellationData = async (
  orgId: string,
  filters?: ConstellationFilters
): Promise<ConstellationAPIResponse> => {
  const params = new URLSearchParams();
  params.append('org_id', orgId);

  if (filters?.levels?.length) {
    params.append('levels', levelsToApiParam(filters.levels));
  }

  if (filters?.plants?.length) {
    params.append('plants', filters.plants.join(','));
  }

  if (filters?.progressRange) {
    params.append('progress_min', filters.progressRange[0].toString());
    params.append('progress_max', filters.progressRange[1].toString());
  }

  if (filters?.cycleId) {
    params.append('cycle_id', filters.cycleId);
  }

  if (filters?.functionArea) {
    params.append('function_area', filters.functionArea);
  }

  if (filters?.groupByFunction) {
    params.append('group_by', 'function');
  }

  const response = await fetch(`${BASE_URL}/api/v1/okr/constellation?${params.toString()}`, {
    headers: getAuthHeaders(),
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch constellation data: ${response.statusText}`);
  }

  const data: ConstellationAPIResponse = await response.json();
  return normalizeConstellationResponse(data);
};

/**
 * Get constellation statistics
 */
export const getConstellationStats = async (
  orgId: string,
  functionArea?: string,
): Promise<any> => {
  const params = new URLSearchParams({ org_id: orgId });
  if (functionArea) params.append('function_area', functionArea);

  const response = await fetch(`${BASE_URL}/api/v1/okr/constellation/stats?${params.toString()}`, {
    headers: getAuthHeaders(),
  });

  if (!response.ok) {
    throw new Error('Failed to fetch constellation stats');
  }

  return response.json();
};

/**
 * Export constellation visualization
 */
export const exportConstellation = async (
  orgId: string,
  format: 'png' | 'svg' | 'pdf' = 'png',
  quality: 'low' | 'medium' | 'high' = 'high'
): Promise<Blob> => {
  const response = await fetch(
    `${BASE_URL}/api/v1/okr/constellation/export`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ org_id: orgId, format, quality }),
    }
  );

  if (!response.ok) {
    throw new Error('Failed to export constellation');
  }

  return response.blob();
};

/**
 * Update node focus
 */
export const focusConstellationNode = async (
  nodeId: string,
  orgId: string
) => {
  const response = await fetch(
    `${BASE_URL}/api/v1/okr/constellation/focus`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ node_id: nodeId, org_id: orgId }),
    }
  );

  if (!response.ok) {
    throw new Error('Failed to focus node');
  }

  return response.json();
};

/**
 * Get node details
 */
export const getNodeDetails = async (
  nodeId: string,
  orgId: string
) => {
  const response = await fetch(
    `${BASE_URL}/api/v1/okr/${nodeId}/details?org_id=${orgId}`,
    {
      headers: getAuthHeaders(),
    }
  );

  if (!response.ok) {
    throw new Error('Failed to fetch node details');
  }

  return response.json();
};

/**
 * Search constellation
 */
export const searchConstellation = async (
  orgId: string,
  query: string
) => {
  const response = await fetch(
    `${BASE_URL}/api/v1/okr/constellation/search?org_id=${orgId}&q=${encodeURIComponent(query)}`,
    {
      headers: getAuthHeaders(),
    }
  );

  if (!response.ok) {
    throw new Error('Failed to search constellation');
  }

  return response.json();
};

export const getConstellationInsights = async (
  orgId: string,
  cycleId?: string,
  functionArea?: string,
): Promise<{ rule_insights: any[]; ai_prescriptions: any[]; metadata: any }> => {
  const params = new URLSearchParams({ org_id: orgId, include_ai: 'true' });
  if (cycleId) params.append('cycle_id', cycleId);
  if (functionArea) params.append('function_area', functionArea);

  const response = await fetch(
    `${BASE_URL}/api/v1/okr/constellation/insights?${params.toString()}`,
    { headers: getAuthHeaders() },
  );
  if (!response.ok) throw new Error('Failed to fetch constellation insights');
  return response.json();
};

export const createObjectiveConnection = async (
  orgId: string,
  objectiveId1: string,
  objectiveId2: string,
  connectionType: 'SUPPORTS' | 'DEPENDS_ON' | 'RELATED_TO',
) => {
  const response = await fetch(
    `${BASE_URL}/api/v1/okr/constellation/connections?org_id=${orgId}`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({
        objective_id_1: objectiveId1,
        objective_id_2: objectiveId2,
        connection_type: connectionType,
      }),
    },
  );
  if (!response.ok) throw new Error('Failed to create connection');
  return response.json();
};

export const constellationApi = {
  getConstellationData,
  exportConstellation,
  getConstellationStats,
  getConstellationInsights,
  createObjectiveConnection,
  focusConstellationNode,
  getNodeDetails,
  searchConstellation,
};
