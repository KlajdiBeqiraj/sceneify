import { Suspense, useEffect, useRef, useState } from "react";
import { useGLTF, TransformControls } from "@react-three/drei";
import type { Group } from "three";
import type { MeshNode, WorldMeshNode } from "../types/scene";
import { assetUrl } from "../hooks/useScene";

function GlbMesh({
  node,
  selected,
  editMode,
  onSelect,
  onTransform,
}: {
  node: MeshNode;
  selected: boolean;
  editMode: boolean;
  onSelect: (id: string) => void;
  onTransform: (id: string, position: number[], rotation: number[], scale: number[]) => void;
}) {
  const url = assetUrl(node.source);
  const gltf = useGLTF(url);
  const group = useRef<Group>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setReady(Boolean(group.current));
  }, [node.id, selected, editMode]);

  return (
    <>
      <group
        ref={group}
        position={node.position as [number, number, number]}
        rotation={node.rotation as [number, number, number]}
        scale={node.scale as [number, number, number]}
        visible={node.visible}
        onClick={(event) => {
          if (!editMode) {
            return;
          }
          event.stopPropagation();
          onSelect(node.id);
        }}
      >
        <primitive object={gltf.scene.clone()} />
      </group>
      {editMode && selected && ready && group.current && (
        <TransformControls
          object={group.current}
          mode="translate"
          onMouseUp={() => {
            const obj = group.current;
            if (!obj) {
              return;
            }
            onTransform(
              node.id,
              [obj.position.x, obj.position.y, obj.position.z],
              [obj.rotation.x, obj.rotation.y, obj.rotation.z],
              [obj.scale.x, obj.scale.y, obj.scale.z],
            );
          }}
        />
      )}
    </>
  );
}

export function MeshAssets({
  meshes,
  editMode,
  selectedId,
  onSelect,
  onTransform,
}: {
  meshes: MeshNode[];
  editMode: boolean;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onTransform: (id: string, position: number[], rotation: number[], scale: number[]) => void;
}) {
  return (
    <>
      {meshes
        .filter((m) => m.visible)
        .map((mesh) => {
          const format = (mesh.format || "").toLowerCase();
          const isGltf =
            format === "glb" || format === "gltf" || /\.gl(b|tf)(\?|$)/i.test(mesh.source);
          if (!isGltf) {
            return null;
          }
          return (
            <Suspense key={mesh.id} fallback={null}>
              <GlbMesh
                node={mesh}
                selected={selectedId === mesh.id}
                editMode={editMode}
                onSelect={onSelect}
                onTransform={onTransform}
              />
            </Suspense>
          );
        })}
    </>
  );
}

export function WorldMeshView({ world }: { world: WorldMeshNode }) {
  if (!world.visible) {
    return null;
  }
  const format = (world.format || "").toLowerCase();
  const isGltf =
    format === "glb" || format === "gltf" || /\.gl(b|tf)(\?|$)/i.test(world.source);
  if (!isGltf) {
    return null;
  }
  return (
    <Suspense fallback={null}>
      <WorldGlb world={world} />
    </Suspense>
  );
}

function WorldGlb({ world }: { world: WorldMeshNode }) {
  const gltf = useGLTF(assetUrl(world.source));
  return (
    <primitive
      object={gltf.scene.clone()}
      position={world.position as [number, number, number]}
      rotation={world.rotation as [number, number, number]}
      scale={world.scale as [number, number, number]}
    />
  );
}
