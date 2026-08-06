import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { TransformControls, useAnimations, useGLTF, useTexture } from "@react-three/drei";
import { Box3, LoopOnce, LoopRepeat, RepeatWrapping, Vector3, type Group, type Mesh, type Object3D, type Texture } from "three";
import { clone as cloneSkeleton } from "three/examples/jsm/utils/SkeletonUtils.js";
import type {
  MeshNode,
  ObjectNode,
  PrimitiveNode,
  SnapSettings,
  TransformMode,
  WorldMeshNode,
} from "../types/scene";
import { assetUrl } from "../hooks/useScene";

type TransformCallback = (
  id: string,
  position: number[],
  rotation: number[],
  scale: number[],
) => void;

function TransformableGroup({
  node,
  selected,
  editMode,
  transformMode,
  snap,
  onSelect,
  onTransform,
  children,
}: {
  node: MeshNode | ObjectNode | PrimitiveNode;
  selected: boolean;
  editMode: boolean;
  transformMode: TransformMode;
  snap: SnapSettings;
  onSelect: (id: string) => void;
  onTransform: TransformCallback;
  children: React.ReactNode;
}) {
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
        {children}
      </group>
      {editMode && selected && ready && group.current && (
        <TransformControls
          object={group.current}
          mode={transformMode}
          translationSnap={snap.translation > 0 ? snap.translation : undefined}
          rotationSnap={
            snap.rotationDegrees > 0
              ? (snap.rotationDegrees * Math.PI) / 180
              : undefined
          }
          scaleSnap={snap.scale > 0 ? snap.scale : undefined}
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

export function GlbVisual({
  node,
  animationState = "idle",
}: {
  node: MeshNode;
  animationState?: "idle" | "move" | "run" | "jump";
}) {
  const gltf = useGLTF(assetUrl(node.source));
  const cloned = useMemo(() => {
    const result = cloneSkeleton(gltf.scene);
    const includeNodes = node.meta?.includeNodes;
    if (includeNodes?.length) {
      result.traverse((child) => {
        const mesh = child as Mesh;
        if (mesh.isMesh) {
          mesh.visible = hasIncludedAncestor(child, includeNodes);
        }
      });
    }
    if (node.meta?.normalizeOrigin) {
      result.updateMatrixWorld(true);
      const bounds = new Box3();
      result.traverse((child) => {
        const mesh = child as Mesh;
        if (mesh.isMesh && mesh.visible) bounds.expandByObject(mesh);
      });
      if (!bounds.isEmpty()) {
        const center = bounds.getCenter(new Vector3());
        result.position.set(-center.x, -bounds.min.y, -center.z);
      }
    }
    return result;
  }, [gltf.scene, node.meta?.includeNodes, node.meta?.normalizeOrigin]);
  const { actions } = useAnimations(gltf.animations, cloned);
  const animation = node.meta?.animation;
  const clipName = animation?.states?.[animationState] ?? animation?.autoplay;

  useEffect(() => {
    cloned.traverse((child) => {
      const mesh = child as Mesh;
      if (mesh.isMesh) {
        mesh.castShadow = true;
        mesh.receiveShadow = true;
      }
    });
  }, [cloned]);

  useEffect(() => {
    if (!clipName) return;
    const action = actions[clipName];
    if (!action) return;
    const fade = animation?.fadeSeconds ?? 0.18;
    action
      .reset()
      .setLoop(animation?.loop === false ? LoopOnce : LoopRepeat, animation?.loop === false ? 1 : Infinity)
      .fadeIn(fade)
      .play();
    return () => {
      action.fadeOut(fade);
    };
  }, [actions, animation?.fadeSeconds, animation?.loop, clipName]);

  return <primitive object={cloned} />;
}

function hasIncludedAncestor(node: Object3D, includeNodes: string[]): boolean {
  let cursor: Object3D | null = node;
  while (cursor) {
    if (includeNodes.some((name) => cursor?.name === name || cursor?.name.includes(name))) {
      return true;
    }
    cursor = cursor.parent;
  }
  return false;
}

export function PrimitiveContent({ node, selected }: { node: PrimitiveNode; selected: boolean }) {
  const size = node.size ?? [1, 1, 1];
  const geometry =
    node.primitive === "sphere" ? (
      <sphereGeometry args={[node.radius ?? 0.5, 24, 18]} />
    ) : node.primitive === "capsule" ? (
      <capsuleGeometry args={[node.radius ?? 0.35, node.height ?? 0.8, 8, 16]} />
    ) : node.primitive === "plane" ? (
      <boxGeometry args={[size[0] ?? 1, Math.min(size[1] ?? 0.04, 0.08), size[2] ?? 1]} />
    ) : (
      <boxGeometry args={[size[0] ?? 1, size[1] ?? 1, size[2] ?? 1]} />
    );
  const opacity = node.material?.opacity ?? 1;
  if (node.material?.baseColorTexture) {
    return <TexturedPrimitiveContent node={node} geometry={geometry} />;
  }
  return (
    <mesh castShadow receiveShadow>
      {geometry}
      <meshStandardMaterial
        color={selected ? "#82a5ff" : (node.material?.color ?? "#7185b7")}
        roughness={node.material?.roughness ?? 0.65}
        metalness={node.material?.metalness ?? 0.05}
        opacity={opacity}
        transparent={opacity < 1}
        wireframe={node.material?.wireframe ?? false}
      />
    </mesh>
  );
}

function TexturedPrimitiveContent({
  node,
  geometry,
}: {
  node: PrimitiveNode;
  geometry: React.ReactNode;
}) {
  const material = node.material!;
  const sources = useMemo(() => {
    const values: Record<string, string> = {
      map: assetUrl(material.baseColorTexture!),
    };
    if (material.normalTexture) values.normalMap = assetUrl(material.normalTexture);
    if (material.metallicRoughnessTexture) {
      values.roughnessMap = assetUrl(material.metallicRoughnessTexture);
      values.metalnessMap = assetUrl(material.metallicRoughnessTexture);
    }
    return values;
  }, [
    material.baseColorTexture,
    material.metallicRoughnessTexture,
    material.normalTexture,
  ]);
  const textures = useTexture(sources) as Record<string, Texture>;
  const repeat = material.textureRepeat ?? [1, 1];

  useEffect(() => {
    Object.values(textures).forEach((texture) => {
      texture.wrapS = RepeatWrapping;
      texture.wrapT = RepeatWrapping;
      texture.repeat.set(repeat[0], repeat[1]);
      texture.needsUpdate = true;
    });
  }, [repeat, textures]);

  return (
    <mesh castShadow receiveShadow>
      {geometry}
      <meshStandardMaterial
        map={textures.map}
        normalMap={textures.normalMap}
        roughnessMap={textures.roughnessMap}
        metalnessMap={textures.metalnessMap}
        color={material.color ?? "#ffffff"}
        roughness={material.roughness ?? 1}
        metalness={material.metalness ?? 1}
      />
    </mesh>
  );
}

export function MeshAssets({
  meshes,
  objects,
  primitives = [],
  editMode,
  selectedId,
  transformMode,
  snap,
  onSelect,
  onTransform,
}: {
  meshes: MeshNode[];
  objects: ObjectNode[];
  primitives?: PrimitiveNode[];
  editMode: boolean;
  selectedId: string | null;
  transformMode: TransformMode;
  snap: SnapSettings;
  onSelect: (id: string) => void;
  onTransform: TransformCallback;
}) {
  const meshById = new Map(meshes.map((mesh) => [mesh.id, mesh]));
  const objectById = new Map(objects.map((object) => [object.id, object]));
  const primitiveById = new Map(primitives.map((primitive) => [primitive.id, primitive]));
  const graphNodes = [...objects, ...meshes, ...primitives];
  const childrenByParent = new Map<string, string[]>();
  const addChild = (parentId: string, childId: string) => {
    const children = childrenByParent.get(parentId) ?? [];
    if (!children.includes(childId)) childrenByParent.set(parentId, [...children, childId]);
  };
  objects.forEach((object) => object.children?.forEach((childId) => addChild(object.id, childId)));
  graphNodes.forEach((node) => {
    if (node.parentId) addChild(node.parentId, node.id);
  });
  const childIds = new Set([...childrenByParent.values()].flat());
  const rootIds = graphNodes
    .filter((node) => !childIds.has(node.id))
    .map((node) => node.id);
  const renderNode = (id: string, ancestors: ReadonlySet<string>): React.ReactNode => {
    if (ancestors.has(id)) {
      return null;
    }
    const nextAncestors = new Set(ancestors).add(id);
    const object = objectById.get(id);
    if (object) {
      return (
        <TransformableGroup
          key={object.id}
          node={object}
          selected={selectedId === object.id}
          editMode={editMode}
          transformMode={transformMode}
          snap={snap}
          onSelect={onSelect}
          onTransform={onTransform}
        >
          {(childrenByParent.get(object.id) ?? []).map((childId) =>
            renderNode(childId, nextAncestors),
          )}
        </TransformableGroup>
      );
    }
    const primitive = primitiveById.get(id);
    if (primitive) {
      if (!primitive.visible) {
        return null;
      }
      return (
        <TransformableGroup
          key={primitive.id}
          node={primitive}
          selected={selectedId === primitive.id}
          editMode={editMode}
          transformMode={transformMode}
          snap={snap}
          onSelect={onSelect}
          onTransform={onTransform}
        >
          {primitive.meta?.renderPrimitive !== false && (
            <PrimitiveContent node={primitive} selected={selectedId === primitive.id} />
          )}
          {(childrenByParent.get(primitive.id) ?? []).map((childId) =>
            renderNode(childId, nextAncestors),
          )}
        </TransformableGroup>
      );
    }
    const mesh = meshById.get(id);
    if (!mesh || !mesh.visible) {
      return null;
    }
    const format = (mesh.format || "").toLowerCase();
    const isGltf =
      format === "glb" ||
      format === "gltf" ||
      /\.gl(b|tf)(\?|$)/i.test(mesh.source);
    if (!isGltf) {
      return null;
    }
    return (
      <Suspense key={mesh.id} fallback={null}>
        <TransformableGroup
          node={mesh}
          selected={selectedId === mesh.id}
          editMode={editMode}
          transformMode={transformMode}
          snap={snap}
          onSelect={onSelect}
          onTransform={onTransform}
        >
          <GlbVisual node={mesh} />
        </TransformableGroup>
      </Suspense>
    );
  };
  const renderIds =
    rootIds.length > 0 ? rootIds : graphNodes.map((node) => node.id);

  return (
    <>
      {renderIds.map((id) => renderNode(id, new Set()))}
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
