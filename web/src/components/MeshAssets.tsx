import { Suspense } from "react";
import { useGLTF } from "@react-three/drei";
import type { MeshNode } from "../types/scene";
import { assetUrl } from "../hooks/useScene";

function GlbMesh({ node }: { node: MeshNode }) {
  const url = assetUrl(node.source);
  const gltf = useGLTF(url);
  return (
    <primitive
      object={gltf.scene.clone()}
      position={node.position as [number, number, number]}
      rotation={node.rotation as [number, number, number]}
      scale={node.scale as [number, number, number]}
      visible={node.visible}
    />
  );
}

export function MeshAssets({ meshes }: { meshes: MeshNode[] }) {
  return (
    <>
      {meshes
        .filter((m) => m.visible)
        .map((mesh) => {
          const format = (mesh.format || "").toLowerCase();
          const isGltf = format === "glb" || format === "gltf" || /\.gl(b|tf)(\?|$)/i.test(mesh.source);
          if (!isGltf) {
            return null;
          }
          return (
            <Suspense key={mesh.id} fallback={null}>
              <GlbMesh node={mesh} />
            </Suspense>
          );
        })}
    </>
  );
}
