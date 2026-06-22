/**
 * Radial OKR Constellation — strict two-level solar-system orbit view
 */

import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  forwardRef,
  useImperativeHandle,
} from "react";
import type {
  ConstellationNode,
  ConstellationEdge,
  RoleScopeConfig,
} from "@/types/constellation.types";
import { useConstellationStore } from "@/store/constellationStore";
import { getScopeConfigFromRole } from "@/utils/roleScopeConfig";
import { drawProgressBands } from "./draw/drawBands";
import { drawCenterNode, centerHitRadius } from "./draw/drawCenterNode";
import { drawOrbitPlanet, planetRadiusForNode } from "./draw/drawPlanetNode";
import { drawOrbitEdge } from "./draw/drawEdges";
import { drawPlanetMoons } from "./draw/drawMoons";
import {
  createStarfield,
  drawDeepSpaceBackground,
  drawGrid,
  drawStarfield,
  type Star,
} from "./draw/drawStarfield";
import { constellationTheme } from "./theme/constellationTheme";
import {
  buildTwoLevelLayout,
  interpolateLayout,
  type TwoLevelLayout,
} from "./orbit/buildTwoLevelLayout";
import { resolveOrbitFocus, resolveDrillTarget } from "./orbit/orbitFocus";
import {
  clampOrbitZoom,
  zoomToLodTier,
  getLodTargets,
  lerpLodOpacity,
  LOD_FADE_MS,
  type LodOpacity,
} from "./orbit/orbitLod";

const ZOOM_WHEEL_SENSITIVITY = 0.00055;
const ZOOM_BUTTON_FACTOR = 1.12;
const WORLD_ORIGIN = { x: 0, y: 0 };
const DRILL_TRANSITION_MS = 450;

interface Props {
  nodes: ConstellationNode[];
  edges?: ConstellationEdge[];
  width?: number;
  height?: number;
  selectedNodeId?: string | null;
  onNodeClick?: (nodeId: string) => void;
  onNodeDoubleClick?: (nodeId: string) => void;
  onClusterExpand?: (clusterId: string) => void;
  showLegend?: boolean;
  showChrome?: boolean;
  title?: string;
  subtitle?: string;
  scopeConfig?: RoleScopeConfig;
  scopeId?: string | null;
  organizationName?: string;
  scopeEntityName?: string;
  useAdaptiveLayout?: boolean;
  matchedNodeIds?: Set<string>;
  visibleGraph?: unknown;
  expandedNodeIds?: Set<string>;
}

export interface OrbitalViewHandle {
  zoomIn: () => void;
  zoomOut: () => void;
  resetView: () => void;
  fitToVisible: () => void;
  getZoom: () => number;
}

function screenToWorld(
  clientX: number,
  clientY: number,
  rect: DOMRect,
  camera: { x: number; y: number },
  zoom: number,
  cx: number,
  cy: number,
): { x: number; y: number } {
  const sx = clientX - rect.left;
  const sy = clientY - rect.top;
  return {
    x: camera.x + (sx - cx) / zoom,
    y: camera.y + (sy - cy) / zoom,
  };
}

function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const handler = () => setReduced(mq.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);
  return reduced;
}

export const OrbitalConstellationView = forwardRef<OrbitalViewHandle, Props>(
  function OrbitalConstellationView(
    {
      nodes,
      edges = [],
      width = 900,
      height = 520,
      selectedNodeId = null,
      onNodeClick,
      scopeConfig: scopeConfigProp,
      scopeId = null,
      organizationName,
      scopeEntityName,
      matchedNodeIds,
      showLegend = false,
      showChrome = false,
      title,
      subtitle,
    },
    ref,
  ) {
    const scopeConfig = scopeConfigProp ?? getScopeConfigFromRole(undefined);
    const displayTitle = title ?? scopeConfig.title;
    const displaySubtitle = subtitle ?? scopeConfig.subtitle;
    const reducedMotion = useReducedMotion();

    const drillDownStack = useConstellationStore((s) => s.drillDownStack);
    const pushDrillDown = useConstellationStore((s) => s.pushDrillDown);

    const containerRef = useRef<HTMLDivElement>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const [measuredSize, setMeasuredSize] = useState({ width: 0, height: 0 });
    const animTimeRef = useRef(0);
    const pulseRef = useRef(0.5);
    const starsRef = useRef<Star[]>([]);
    const [camera, setCamera] = useState({ x: WORLD_ORIGIN.x, y: WORLD_ORIGIN.y });
    const [zoom, setZoom] = useState(1);
    const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
    const initialFitDoneRef = useRef(false);
    const lodOpacityRef = useRef<LodOpacity>(getLodTargets("mid"));
    const lodTargetRef = useRef<LodOpacity>(getLodTargets("mid"));
    const lodFadeStartRef = useRef(performance.now());

    const transitionRef = useRef<{
      from: TwoLevelLayout;
      to: TwoLevelLayout;
      focalPlanetId: string;
      start: number;
    } | null>(null);
    const prevFocusKeyRef = useRef("");
    const lastDrillPlanetRef = useRef("");
    const prevLayoutRef = useRef<TwoLevelLayout | null>(null);

    const dragRef = useRef<{ active: boolean; lastX: number; lastY: number }>({
      active: false,
      lastX: 0,
      lastY: 0,
    });

    useEffect(() => {
      const el = containerRef.current;
      if (!el) return;
      const update = () => {
        const w = el.clientWidth;
        const h = el.clientHeight;
        if (w > 0 && h > 0) setMeasuredSize({ width: w, height: h });
      };
      update();
      const ro = new ResizeObserver(update);
      ro.observe(el);
      return () => ro.disconnect();
    }, []);

    const effectiveWidth = measuredSize.width > 0 ? measuredSize.width : width;
    const effectiveHeight = measuredSize.height > 0 ? measuredSize.height : height;
    const cx = effectiveWidth / 2;
    const cy = effectiveHeight / 2;
    const canvasHeight = showChrome ? effectiveHeight - 120 : effectiveHeight;

    useEffect(() => {
      starsRef.current = createStarfield(effectiveWidth, canvasHeight);
    }, [effectiveWidth, canvasHeight]);

    const focus = useMemo(
      () =>
        resolveOrbitFocus(
          drillDownStack,
          scopeConfig,
          scopeId,
          organizationName,
          scopeEntityName,
        ),
      [drillDownStack, scopeConfig, scopeId, organizationName, scopeEntityName],
    );

    const focusKey = `${focus.scopeLevel}:${focus.scopeId}:${focus.label}`;

    const targetLayout = useMemo(() => {
      try {
        return buildTwoLevelLayout(nodes, focus, organizationName);
      } catch {
        return null;
      }
    }, [nodes, focus, organizationName]);

    useEffect(() => {
      if (!targetLayout) return;
      if (prevFocusKeyRef.current && prevFocusKeyRef.current !== focusKey) {
        transitionRef.current = {
          from: prevLayoutRef.current ?? targetLayout,
          to: targetLayout,
          focalPlanetId: lastDrillPlanetRef.current,
          start: performance.now(),
        };
        if (reducedMotion) {
          transitionRef.current = null;
        }
      }
      prevFocusKeyRef.current = focusKey;
      prevLayoutRef.current = targetLayout;
    }, [focusKey, targetLayout, reducedMotion]);

    const getDisplayLayout = useCallback((): TwoLevelLayout | null => {
      if (!targetLayout) return null;
      const tr = transitionRef.current;
      if (!tr || reducedMotion) return targetLayout;
      const t = Math.min(1, (performance.now() - tr.start) / DRILL_TRANSITION_MS);
      if (t >= 1) {
        transitionRef.current = null;
        return targetLayout;
      }
      return interpolateLayout(tr.from, tr.to, t, tr.focalPlanetId);
    }, [targetLayout, reducedMotion]);

    const fitToLayout = useCallback(() => {
      const layout = targetLayout;
      if (!layout) return;
      const all = [
        { x: WORLD_ORIGIN.x, y: WORLD_ORIGIN.y },
        ...layout.planets.map((p) => ({ x: p.x, y: p.y })),
      ];
      let minX = Infinity;
      let minY = Infinity;
      let maxX = -Infinity;
      let maxY = -Infinity;
      for (const p of all) {
        minX = Math.min(minX, p.x);
        minY = Math.min(minY, p.y);
        maxX = Math.max(maxX, p.x);
        maxY = Math.max(maxY, p.y);
      }
      const pad = 140;
      const graphW = maxX - minX + pad * 2;
      const graphH = maxY - minY + pad * 2;
      const scale = clampOrbitZoom(
        Math.max(0.55, Math.min(effectiveWidth / graphW, effectiveHeight / graphH, 1.2)),
      );
      setZoom(scale);
      setCamera({ x: (minX + maxX) / 2, y: (minY + maxY) / 2 });
    }, [targetLayout, effectiveWidth, effectiveHeight]);

    useImperativeHandle(
      ref,
      () => ({
        zoomIn: () => setZoom((z) => clampOrbitZoom(z * ZOOM_BUTTON_FACTOR)),
        zoomOut: () => setZoom((z) => clampOrbitZoom(z / ZOOM_BUTTON_FACTOR)),
        resetView: () => fitToLayout(),
        fitToVisible: () => fitToLayout(),
        getZoom: () => zoom,
      }),
      [zoom, fitToLayout],
    );

    useEffect(() => {
      if (initialFitDoneRef.current || !targetLayout?.planets.length) return;
      fitToLayout();
      initialFitDoneRef.current = true;
    }, [targetLayout, fitToLayout]);

    useEffect(() => {
      const tier = zoomToLodTier(zoom);
      lodTargetRef.current = getLodTargets(tier);
      lodFadeStartRef.current = performance.now();
    }, [zoom]);

    const drawFrame = useCallback(() => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext("2d");
      if (!ctx || !targetLayout) return;

      const layout = getDisplayLayout() ?? targetLayout;
      const time = animTimeRef.current;
      const pulse = pulseRef.current;

      const lodT = Math.min(1, (performance.now() - lodFadeStartRef.current) / LOD_FADE_MS);
      lodOpacityRef.current = lerpLodOpacity(lodOpacityRef.current, lodTargetRef.current, lodT);

      const dpr = window.devicePixelRatio || 1;
      canvas.width = effectiveWidth * dpr;
      canvas.height = canvasHeight * dpr;
      canvas.style.width = `${effectiveWidth}px`;
      canvas.style.height = `${canvasHeight}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      drawDeepSpaceBackground(ctx, effectiveWidth, canvasHeight);
      drawStarfield(
        ctx,
        starsRef.current,
        time,
        effectiveWidth,
        canvasHeight,
        camera.x,
        camera.y,
        reducedMotion,
      );

      ctx.save();
      ctx.translate(cx, cy);
      ctx.scale(zoom, zoom);
      ctx.translate(-camera.x, -camera.y);

      drawGrid(ctx, camera.x, camera.y, effectiveWidth, canvasHeight, zoom);
      drawProgressBands(ctx, WORLD_ORIGIN.x, WORLD_ORIGIN.y, lodOpacityRef.current.bandLabels);

      const lod = lodOpacityRef.current;
      const tr = transitionRef.current;
      const transitionT = tr
        ? Math.min(1, (performance.now() - tr.start) / DRILL_TRANSITION_MS)
        : 1;
      const fadeOut = tr && transitionT < 0.5 ? 1 - transitionT * 2 : 1;
      const fadeIn = tr && transitionT > 0.5 ? (transitionT - 0.5) * 2 : tr ? 0 : 1;

      if (edges.length && layout.planets.length) {
        const nodePos = new Map<string, { x: number; y: number }>();
        nodePos.set(layout.center.id, { x: WORLD_ORIGIN.x, y: WORLD_ORIGIN.y });
        for (const p of layout.planets) {
          nodePos.set(p.node.id, { x: p.x, y: p.y });
        }
        for (const edge of edges) {
          const from = nodePos.get(edge.source);
          const to = nodePos.get(edge.target);
          if (!from || !to) continue;
          const edgeActive =
            hoveredNodeId === edge.source || hoveredNodeId === edge.target;
          drawOrbitEdge(ctx, from.x, from.y, to.x, to.y, edge, edgeActive);
        }
      }

      drawCenterNode(ctx, WORLD_ORIGIN.x, WORLD_ORIGIN.y, layout.center, {
        pulse,
        hovered: hoveredNodeId === layout.center.id,
        selected: selectedNodeId === layout.center.id,
        zoom,
      });

      for (const placed of layout.planets) {
        const { node, x, y } = placed;
        const prog = node.final_progress ?? node.progress ?? 0;
        const isSelected = selectedNodeId === node.id;
        const isContextOnly = matchedNodeIds && !matchedNodeIds.has(node.id);
        const isFocal = tr?.focalPlanetId === node.id && transitionT < 1;

        drawOrbitPlanet(ctx, x, y, node, {
          progress: prog,
          health: node.alignment_health,
          hovered: hoveredNodeId === node.id,
          selected: isSelected,
          dimmed: !!isContextOnly,
          zoom,
          showProgressArc: lod.progressArcs > 0.05,
          showProgressLabel: lod.planetProgress > 0.05,
          moonCountBadge:
            lod.moonCountBadge > 0.05 && placed.totalMoonCount > 0
              ? placed.totalMoonCount
              : null,
          radius: placed.visualRadius,
          opacity: isFocal ? fadeIn || fadeOut : fadeOut,
        });

        if (lod.moonDots > 0.05) {
          drawPlanetMoons(
            ctx,
            placed,
            time,
            reducedMotion,
            hoveredNodeId === node.id,
            zoom,
            lod,
          );
        }
      }

      ctx.restore();
    }, [
      targetLayout,
      getDisplayLayout,
      edges,
      effectiveWidth,
      canvasHeight,
      camera,
      zoom,
      cx,
      cy,
      selectedNodeId,
      matchedNodeIds,
      hoveredNodeId,
      reducedMotion,
    ]);

    useEffect(() => {
      let frameId: number;
      const loop = (now: number) => {
        if (!reducedMotion) {
          animTimeRef.current = now * 0.001;
          pulseRef.current =
            Math.sin(animTimeRef.current * constellationTheme.center.pulseSpeed) * 0.5 + 0.5;
        } else {
          pulseRef.current = 0.5;
        }
        drawFrame();
        frameId = requestAnimationFrame(loop);
      };
      frameId = requestAnimationFrame(loop);
      return () => cancelAnimationFrame(frameId);
    }, [drawFrame, reducedMotion]);

    const hitTest = useCallback(
      (clientX: number, clientY: number): string | null => {
        const layout = getDisplayLayout() ?? targetLayout;
        if (!layout) return null;
        const canvas = canvasRef.current;
        if (!canvas) return null;
        const rect = canvas.getBoundingClientRect();
        const { x, y } = screenToWorld(clientX, clientY, rect, camera, zoom, cx, cy);

        const cdx = x - WORLD_ORIGIN.x;
        const cdy = y - WORLD_ORIGIN.y;
        if (cdx * cdx + cdy * cdy < centerHitRadius() ** 2) return layout.center.id;

        for (let i = layout.planets.length - 1; i >= 0; i--) {
          const placed = layout.planets[i];
          const r = placed.visualRadius + 8;
          const dx = x - placed.x;
          const dy = y - placed.y;
          if (dx * dx + dy * dy < r * r) return placed.node.id;
        }
        return null;
      },
      [getDisplayLayout, targetLayout, camera, zoom, cx, cy],
    );

    const lastClickRef = useRef<{ id: string; t: number } | null>(null);
    const lastEmptyClickRef = useRef<{ t: number; x: number; y: number } | null>(null);

    const onMouseDown = (e: React.MouseEvent) => {
      const hit = hitTest(e.clientX, e.clientY);
      if (hit) {
        lastEmptyClickRef.current = null;
        const now = Date.now();
        const layout = getDisplayLayout() ?? targetLayout;
        const planet = layout?.planets.find((p) => p.node.id === hit)?.node;

        if (lastClickRef.current?.id === hit && now - lastClickRef.current.t < 400) {
          if (planet) {
            const drill = resolveDrillTarget(planet);
            if (drill) {
              lastDrillPlanetRef.current = hit;
              pushDrillDown(drill);
            }
          }
          lastClickRef.current = null;
          return;
        }
        lastClickRef.current = { id: hit, t: now };
        onNodeClick?.(hit);
        return;
      }

      const now = Date.now();
      const prev = lastEmptyClickRef.current;
      if (
        prev &&
        now - prev.t < 400 &&
        Math.hypot(e.clientX - prev.x, e.clientY - prev.y) < 14
      ) {
        fitToLayout();
        setZoom(1);
        lastEmptyClickRef.current = null;
        lastClickRef.current = null;
        return;
      }
      lastEmptyClickRef.current = { t: now, x: e.clientX, y: e.clientY };
      lastClickRef.current = null;
      dragRef.current = { active: true, lastX: e.clientX, lastY: e.clientY };
    };

    const onWheel = (e: React.WheelEvent) => {
      e.preventDefault();
      const canvas = canvasRef.current;
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      const sx = e.clientX - rect.left;
      const sy = e.clientY - rect.top;
      const worldBefore = screenToWorld(e.clientX, e.clientY, rect, camera, zoom, cx, cy);
      const factor = Math.exp(-e.deltaY * ZOOM_WHEEL_SENSITIVITY);
      const newZoom = clampOrbitZoom(zoom * factor);
      setCamera({
        x: worldBefore.x - (sx - cx) / newZoom,
        y: worldBefore.y - (sy - cy) / newZoom,
      });
      setZoom(newZoom);
    };

    const avgProgress =
      nodes.length > 0
        ? Math.round(
            nodes.reduce((s, n) => s + (n.final_progress ?? n.progress ?? 0), 0) / nodes.length,
          )
        : 0;

    return (
      <div
        ref={containerRef}
        className={`relative flex w-full h-full ${showChrome ? "rounded-xl border border-slate-800 bg-slate-950 overflow-hidden" : ""}`}
      >
        <div className="flex-1 flex flex-col min-w-0 w-full h-full">
          {showChrome && (
            <div className="px-4 pt-4 pb-2 border-b border-slate-800/80">
              <h2 className="text-lg font-semibold text-slate-100">{displayTitle}</h2>
              <p className="text-xs text-slate-400 mt-0.5">{displaySubtitle}</p>
            </div>
          )}
          <canvas
            ref={canvasRef}
            className="cursor-grab active:cursor-grabbing w-full h-full block"
            style={{ width: effectiveWidth, height: canvasHeight }}
            onWheel={onWheel}
            onMouseDown={onMouseDown}
            onMouseMove={(e) => {
              if (dragRef.current.active) {
                const dx = e.clientX - dragRef.current.lastX;
                const dy = e.clientY - dragRef.current.lastY;
                dragRef.current.lastX = e.clientX;
                dragRef.current.lastY = e.clientY;
                setCamera((c) => ({
                  x: c.x - dx / zoom,
                  y: c.y - dy / zoom,
                }));
                return;
              }
              const hit = hitTest(e.clientX, e.clientY);
              setHoveredNodeId(hit);
              const canvas = canvasRef.current;
              if (canvas) canvas.style.cursor = hit ? "pointer" : "grab";
            }}
            onMouseUp={() => {
              dragRef.current.active = false;
            }}
            onMouseLeave={() => {
              dragRef.current.active = false;
              setHoveredNodeId(null);
            }}
          />
          {showChrome && (
            <div className="px-4 py-2 border-t border-slate-800/80 flex items-center gap-3 text-xs text-slate-400">
              <span>Overall progress</span>
              <div className="flex-1 h-1.5 rounded-full bg-slate-800 overflow-hidden max-w-xs">
                <div
                  className="h-full rounded-full bg-cyan-500"
                  style={{ width: `${Math.min(100, avgProgress)}%` }}
                />
              </div>
              <span className="text-cyan-400 font-medium">{avgProgress}%</span>
            </div>
          )}
        </div>
        {showLegend && (
          <aside className="w-56 shrink-0 border-l border-slate-800 bg-slate-900/80 p-4 text-xs space-y-3">
            <h3 className="font-semibold text-slate-200">Legend</h3>
            <p className="text-slate-400">
              Center + direct children only · Double-click planet to drill down · Scroll to zoom
            </p>
            <p className="text-slate-500 pt-1 border-t border-slate-800">
              Inner ring ≥70% · Mid 40–70% · Outer &lt;40%
            </p>
          </aside>
        )}
      </div>
    );
  },
);
