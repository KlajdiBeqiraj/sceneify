import { useEffect, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls, Grid, Environment } from "@react-three/drei";
import { fetchScene } from "../hooks/useScene";
import type { ScenePayload } from "../types/scene";
import { MeshAssets } from "./MeshAssets";
import { Annotations } from "./Annotations";
import { Trajectories } from "./Trajectories";

export function App() {
  const [scene, setScene] = useState<ScenePayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchScene()
      .then(setScene)
      .catch((err: Error) => setError(err.message));
  }, []);

  if (error) {
    return <div className="panel error">Could not load scene: {error}</div>;
  }

  if (!scene) {
    return <div className="panel">Loading sceneify…</div>;
  }

  return (
    <div className="shell">
      <header className="topbar">
        <strong>sceneify</strong>
        <span>{scene.name}</span>
        <span>
          {scene.meshes.length} meshes · {scene.annotations.length} annotations ·{" "}
          {scene.trajectories.length} trajectories
        </span>
      </header>
      <Canvas camera={{ position: [2.5, 1.8, 3.5], fov: 50 }}>
        <color attach="background" args={[scene.background]} />
        <ambientLight intensity={0.55} />
        <directionalLight position={[4, 6, 2]} intensity={1.1} />
        <Environment preset="city" />
        <Grid infiniteGrid fadeDistance={28} sectionColor="#3a3f4b" cellColor="#23262e" />
        <MeshAssets meshes={scene.meshes} />
        <Annotations items={scene.annotations} />
        <Trajectories items={scene.trajectories} />
        <OrbitControls makeDefault />
      </Canvas>
    </div>
  );
}
