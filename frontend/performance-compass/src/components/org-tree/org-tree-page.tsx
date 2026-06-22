import { useMemo, useState, useEffect } from "react";
import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import {
  ChevronDown,
  ChevronRight,
  Search,
  GitBranch,
  Users,
  Target,
  Loader2,
  Building2,
  Factory,
  Network,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useOrgTree, useOrgNodeDetail } from "@/lib/hooks";
import { flattenOrgNodes } from "@/lib/org-tree-utils";
import { api, type OrgNode, type NodeType } from "@/lib/api";

const NODE_ICONS: Partial<Record<NodeType, React.ElementType>> = {
  ORGANIZATION: Building2,
  REGION: Network,
  CORPORATE_FUNCTION: GitBranch,
  PLANT: Factory,
  DEPARTMENT: GitBranch,
  TEAM: Users,
};

interface Props {
  focusNodeId?: string;
}

function getRoots(tree: OrgNode | { roots: OrgNode[] }): OrgNode[] {
  if (tree && typeof tree === "object" && "roots" in tree) {
    return (tree as { roots: OrgNode[] }).roots;
  }
  return [tree as OrgNode];
}

function OrgTreeNodeRow({
  node,
  depth,
  selectedId,
  expandedIds,
  onSelect,
  onToggle,
  searchLower,
  matchIds,
}: {
  node: OrgNode;
  depth: number;
  selectedId?: string;
  expandedIds: Set<string>;
  onSelect: (id: string) => void;
  onToggle: (id: string) => void;
  searchLower: string;
  matchIds: Set<string>;
}) {
  const hasChildren = (node.children?.length ?? 0) > 0;
  const expanded = expandedIds.has(node.id);
  const Icon = NODE_ICONS[node.node_type] || Building2;
  const visible =
    !searchLower ||
    node.name.toLowerCase().includes(searchLower) ||
    matchIds.has(node.id);

  if (!visible) return null;

  const showChildren = hasChildren && expanded;

  return (
    <div>
      <button
        type="button"
        className={`flex w-full items-center gap-1 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted/60 ${
          selectedId === node.id ? "bg-primary/10 text-primary" : ""
        }`}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
        onClick={() => onSelect(node.id)}
      >
        {hasChildren ? (
          <span
            className="shrink-0 p-0.5"
            onClick={(e) => {
              e.stopPropagation();
              onToggle(node.id);
            }}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === "Enter" && onToggle(node.id)}
          >
            {expanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
          </span>
        ) : (
          <span className="w-4 shrink-0" />
        )}
        <Icon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        <span className="truncate flex-1">{node.name}</span>
        <Badge variant="outline" className="text-[9px] px-1 py-0 shrink-0">
          {node.node_type.replace("_", " ")}
        </Badge>
      </button>
      {showChildren &&
        node.children!.map((ch) => (
          <OrgTreeNodeRow
            key={ch.id}
            node={ch}
            depth={depth + 1}
            selectedId={selectedId}
            expandedIds={expandedIds}
            onSelect={onSelect}
            onToggle={onToggle}
            searchLower={searchLower}
            matchIds={matchIds}
          />
        ))}
    </div>
  );
}

function NodeDetailPanel({ nodeId, flatNodes }: { nodeId: string; flatNodes: OrgNode[] }) {
  const detailQuery = useOrgNodeDetail(nodeId, true);
  const node = detailQuery.data;
  const flat = flatNodes.find((n) => n.id === nodeId);

  const scopeFilter = useMemo(() => {
    if (!node) return {};
    const t = node.node_type;
    if (t === "PLANT") return { plant_id: node.id };
    if (t === "DEPARTMENT") return { department_id: node.id };
    if (t === "TEAM") return { team_id: node.id };
    return {};
  }, [node]);

  const { data: objectives = [] } = useQuery({
    queryKey: ["objectives", "node", nodeId, scopeFilter],
    queryFn: () => api.getObjectives(scopeFilter as Parameters<typeof api.getObjectives>[0]),
    enabled: !!node && Object.keys(scopeFilter).length > 0,
  });

  const { data: employees = [] } = useQuery({
    queryKey: ["employees", "node", nodeId, scopeFilter],
    queryFn: () => api.getEmployees({ ...scopeFilter, is_active: true }),
    enabled: !!node && Object.keys(scopeFilter).length > 0,
  });

  const functionalParent = flatNodes.find((n) => n.id === node?.functional_parent_id);

  if (detailQuery.isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!node) {
    return <p className="text-sm text-muted-foreground p-4">Node not found.</p>;
  }

  return (
    <div className="space-y-4 p-4">
      <div>
        <h3 className="text-lg font-semibold">{node.name}</h3>
        <div className="flex flex-wrap gap-1.5 mt-1">
          <Badge variant="outline">{node.node_type.replace("_", " ")}</Badge>
          {node.code && <Badge variant="secondary">{node.code}</Badge>}
        </div>
        <p className="text-xs text-muted-foreground mt-1 font-mono">path: {node.path}</p>
      </div>

      {node.functional_parent_id && (
        <Card className="border-dashed">
          <CardHeader className="py-2 px-3">
            <CardTitle className="text-xs font-medium text-muted-foreground">Functional parent (dotted line)</CardTitle>
          </CardHeader>
          <CardContent className="py-2 px-3 text-sm">
            {functionalParent ? functionalParent.name : node.functional_parent_id}
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-2 gap-2 text-sm">
        <div className="rounded-md border p-2">
          <p className="text-xs text-muted-foreground">Child nodes</p>
          <p className="font-semibold">{node.children?.length ?? 0}</p>
        </div>
        {Object.keys(scopeFilter).length > 0 && (
          <>
            <div className="rounded-md border p-2">
              <p className="text-xs text-muted-foreground flex items-center gap-1">
                <Users className="h-3 w-3" /> Members
              </p>
              <p className="font-semibold">{employees.length}</p>
            </div>
            <div className="rounded-md border p-2 col-span-2">
              <p className="text-xs text-muted-foreground flex items-center gap-1">
                <Target className="h-3 w-3" /> OKRs at this node
              </p>
              <p className="font-semibold">{objectives.length}</p>
              {objectives.length > 0 && (
                <ul className="mt-2 space-y-1">
                  {objectives.slice(0, 5).map((o) => (
                    <li key={o.id}>
                      <Link to="/okrs" className="text-xs text-primary hover:underline">
                        {o.title}
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </>
        )}
      </div>

      <Button variant="outline" size="sm" asChild>
        <Link to="/hierarchy">Manage regions & corporate functions</Link>
      </Button>
    </div>
  );
}

export function OrgTreePage({ focusNodeId }: Props) {
  const treeQuery = useOrgTree(true);
  const [selectedId, setSelectedId] = useState<string | undefined>(focusNodeId);
  const [search, setSearch] = useState("");
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (focusNodeId) setSelectedId(focusNodeId);
  }, [focusNodeId]);

  const flatNodes = useMemo(() => {
    if (!treeQuery.data) return [];
    return flattenOrgNodes(treeQuery.data);
  }, [treeQuery.data]);

  const roots = useMemo(() => (treeQuery.data ? getRoots(treeQuery.data) : []), [treeQuery.data]);

  const searchLower = search.trim().toLowerCase();

  const matchIds = useMemo(() => {
    const ids = new Set<string>();
    if (!searchLower) return ids;
    for (const n of flatNodes) {
      if (n.name.toLowerCase().includes(searchLower)) {
        ids.add(n.id);
        for (const part of (n.path || "").split(".")) {
          if (part) ids.add(part);
        }
      }
    }
    return ids;
  }, [flatNodes, searchLower]);

  useEffect(() => {
    if (searchLower && matchIds.size) {
      setExpandedIds((prev) => new Set([...prev, ...matchIds]));
    }
  }, [searchLower, matchIds]);

  const toggleExpand = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  useEffect(() => {
    if (!selectedId && roots.length) {
      setSelectedId(roots[0].id);
      setExpandedIds(new Set(roots.map((r) => r.id)));
    }
  }, [roots, selectedId]);

  if (treeQuery.isLoading) {
    return (
      <div className="flex justify-center py-16">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (treeQuery.error) {
    return (
      <p className="text-sm text-destructive p-4">
        {treeQuery.error instanceof Error ? treeQuery.error.message : "Failed to load org tree"}
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-semibold flex items-center gap-2">
          <Network className="h-6 w-6 text-primary" />
          Organization Tree
        </h2>
        <p className="text-sm text-muted-foreground mt-0.5">
          Explore regions, plants, departments, and teams. Scope reflects your permissions.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(280px,360px)_1fr] min-h-[480px]">
        <Card className="overflow-hidden">
          <CardHeader className="py-3 px-3 border-b">
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search nodes..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-8 h-9"
              />
            </div>
          </CardHeader>
          <ScrollArea className="h-[420px]">
            <div className="p-1">
              {roots.map((root) => (
                <OrgTreeNodeRow
                  key={root.id}
                  node={root}
                  depth={0}
                  selectedId={selectedId}
                  expandedIds={expandedIds}
                  onSelect={setSelectedId}
                  onToggle={toggleExpand}
                  searchLower={searchLower}
                  matchIds={matchIds}
                />
              ))}
            </div>
          </ScrollArea>
        </Card>

        <Card>
          {selectedId ? (
            <NodeDetailPanel nodeId={selectedId} flatNodes={flatNodes} />
          ) : (
            <CardContent className="py-12 text-center text-muted-foreground text-sm">
              Select a node to view details
            </CardContent>
          )}
        </Card>
      </div>
    </div>
  );
}
