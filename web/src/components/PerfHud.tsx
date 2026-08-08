import { useFrame, useThree } from "@react-three/fiber";
import { useEffect, useRef, useState } from "react";
import type { InstancedMesh, Mesh, Object3D } from "three";

export type PerfSample = {
  fps: number;
  calls: number;
  triangles: number;
  geometries: number;
  textures: number;
  minFps: number;
  samples: number;
  meshObjects: number;
  instancedMeshes: number;
  instancedCount: number;
};

declare global {
  interface Window {
    __SCENEIFY_PERF__?: PerfSample;
  }
}

const PERF_EVENT = "sceneify-perf";

function publish(sample: PerfSample) {
  window.__SCENEIFY_PERF__ = sample;
  let el = document.getElementById("sceneify-perf-metrics");
  if (!el) {
    el = document.createElement("div");
    el.id = "sceneify-perf-metrics";
    el.dataset.testid = "sceneify-perf-metrics";
    el.hidden = true;
    document.body.appendChild(el);
  }
  el.dataset.fps = String(sample.fps);
  el.dataset.calls = String(sample.calls);
  el.dataset.triangles = String(sample.triangles);
  el.dataset.geometries = String(sample.geometries);
  el.dataset.textures = String(sample.textures);
  el.dataset.minFps = String(sample.minFps);
  el.dataset.samples = String(sample.samples);
  el.dataset.meshObjects = String(sample.meshObjects);
  el.dataset.instancedMeshes = String(sample.instancedMeshes);
  el.dataset.instancedCount = String(sample.instancedCount);
  el.textContent = JSON.stringify(sample);
  window.dispatchEvent(new CustomEvent(PERF_EVENT, { detail: sample }));
}

function countSceneGraph(root: Object3D) {
  let meshObjects = 0;
  let instancedMeshes = 0;
  let instancedCount = 0;
  root.traverse((object) => {
    const instanced = object as InstancedMesh;
    if (instanced.isInstancedMesh) {
      instancedMeshes += 1;
      instancedCount += instanced.count;
      return;
    }
    const mesh = object as Mesh;
    if (mesh.isMesh) meshObjects += 1;
  });
  return { meshObjects, instancedMeshes, instancedCount };
}

/**
 * R3F-safe sampler: no DOM JSX inside the Canvas reconciler.
 * Enable with ?perf=1; reads via window.__SCENEIFY_PERF__ or #sceneify-perf-metrics.
 */
export function PerfHud() {
  const { gl, scene } = useThree();
  const frames = useRef({
    count: 0,
    last: performance.now(),
    minFps: Number.POSITIVE_INFINITY,
    samples: 0,
    peakCalls: 0,
    peakTriangles: 0,
  });

  useEffect(() => {
    gl.info.autoReset = false;
    return () => {
      gl.info.autoReset = true;
    };
  }, [gl]);

  // Priority > 0 runs after render when the renderer supports it.
  useFrame(() => {
    const info = gl.info;
    frames.current.count += 1;
    frames.current.peakCalls = Math.max(frames.current.peakCalls, info.render.calls);
    frames.current.peakTriangles = Math.max(frames.current.peakTriangles, info.render.triangles);
    info.reset();

    const now = performance.now();
    if (now - frames.current.last < 500) {
      return;
    }
    const fps = Math.round((frames.current.count * 1000) / (now - frames.current.last));
    const calls = frames.current.peakCalls;
    const triangles = frames.current.peakTriangles;
    const graph = countSceneGraph(scene);
    frames.current.count = 0;
    frames.current.last = now;
    frames.current.samples += 1;
    frames.current.peakCalls = 0;
    frames.current.peakTriangles = 0;
    if (fps > 0) {
      frames.current.minFps = Math.min(frames.current.minFps, fps);
    }
    publish({
      fps,
      calls,
      triangles,
      geometries: info.memory.geometries,
      textures: info.memory.textures,
      minFps: Number.isFinite(frames.current.minFps) ? frames.current.minFps : fps,
      samples: frames.current.samples,
      ...graph,
    });
  }, 1);

  return null;
}

/** DOM overlay outside the R3F Canvas. */
export function PerfOverlay() {
  const [stats, setStats] = useState<PerfSample | null>(null);
  useEffect(() => {
    const onPerf = (event: Event) => {
      setStats((event as CustomEvent<PerfSample>).detail);
    };
    window.addEventListener(PERF_EVENT, onPerf);
    if (window.__SCENEIFY_PERF__) setStats(window.__SCENEIFY_PERF__);
    return () => window.removeEventListener(PERF_EVENT, onPerf);
  }, []);
  if (!stats) return null;
  return (
    <div className="perf-hud" aria-hidden="true">
      <strong>{stats.fps} fps</strong>
      <span>min {stats.minFps}</span>
      <span>{stats.calls} draws</span>
      <span>{stats.instancedCount} inst</span>
      <span>{stats.meshObjects} mesh</span>
      <span>{stats.triangles} tris</span>
    </div>
  );
}
