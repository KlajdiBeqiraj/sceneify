import { useEffect, useMemo, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls, Grid, Environment } from "@react-three/drei";
import { fetchScene, patchNode, saveScene } from "../hooks/useScene";
import type { ScenePayload } from "../types/scene";
import { MeshAssets, WorldMeshView } from "./MeshAssets";
import { Annotations } from "./Annotations";
import { Trajectories } from "./Trajectories";
import { EnvironmentViz } from "./EnvironmentViz";
import { SidePanel } from "./SidePanel";

export function App() {
  const [scene, setScene] = useState<ScenePayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editMode, setEditMode] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [savePath, setSavePath] = useState("world.sceneify.json");
  const [status, setStatus] = useState<string>("");

  useEffect(() => {
    fetchScene()
      .then(setScene)
      .catch((err: Error) => setError(err.message));
  }, []);

  const env = scene?.environment;
  const stats = useMemo(() => {
    if (!scene) {
      return "";
    }
    const ruleCount = env?.rules?.length ?? 0;
    const zoneCount = env?.zones?.length ?? 0;
    return `${scene.meshes.length} meshes · ${scene.annotations.length} annotations · ${scene.trajectories.length} trajectories${
      env ? ` · env ${ruleCount} rules / ${zoneCount} zones` : ""
    }`;
  }, [scene, env]);

  async function applyPatch(
    id: string,
    patch: { position?: number[]; rotation?: number[]; scale?: number[] },
  ) {
    try {
      const result = await patchNode(id, patch);
      setScene(result.scene);
      setStatus(`Updated ${id}`);
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Update failed");
    }
  }

  async function onSave() {
    try {
      const saved = await saveScene(savePath);
      setStatus(`Saved ${saved}`);
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Save failed");
    }
  }

  if (error) {
    return <div className="panel error">Could not load scene: {error}</div>;
  }

  if (!scene) {
    return <div className="panel">Loading sceneify…</div>;
  }

  return (
    <div className={editMode ? "shell edit" : "shell"}>
      <header className="topbar">
        <strong>sceneify</strong>
        <span>{scene.name}</span>
        <span>{stats}</span>
        <button
          type="button"
          className={editMode ? "btn active" : "btn"}
          onClick={() => setEditMode((value) => !value)}
        >
          {editMode ? "Edit on" : "Edit off"}
        </button>
        {status && <span className="status">{status}</span>}
      </header>
      <div className="workspace">
        {editMode && (
          <SidePanel
            scene={scene}
            selectedId={selectedId}
            editMode={editMode}
            onSelect={setSelectedId}
            onChangeNode={applyPatch}
            onSave={onSave}
            savePath={savePath}
            onSavePathChange={setSavePath}
          />
        )}
        <Canvas camera={{ position: [2.5, 1.8, 3.5], fov: 50 }}>
          <color attach="background" args={[scene.background]} />
          <ambientLight intensity={0.55} />
          <directionalLight position={[4, 6, 2]} intensity={1.1} />
          <Environment preset="city" />
          <Grid infiniteGrid fadeDistance={28} sectionColor="#3a3f4b" cellColor="#23262e" />
          <EnvironmentViz environment={env} />
          {env?.worldMesh && <WorldMeshView world={env.worldMesh} />}
          <MeshAssets
            meshes={scene.meshes}
            editMode={editMode}
            selectedId={selectedId}
            onSelect={setSelectedId}
            onTransform={(id, position, rotation, scale) =>
              applyPatch(id, { position, rotation, scale })
            }
          />
          <Annotations items={scene.annotations} />
          <Trajectories items={scene.trajectories} />
          <OrbitControls makeDefault enabled={!editMode || !selectedId} />
        </Canvas>
      </div>
    </div>
  );
}
