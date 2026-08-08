import { Suspense, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  Detailed,
  TransformControls,
  useAnimations,
  useGLTF,
  useTexture,
} from "@react-three/drei";
import {
  Box3,
  LoopOnce,
  LoopRepeat,
  Object3D,
  RepeatWrapping,
  Vector3,
  type Group,
  type InstancedMesh,
  type Mesh,
  type Object3D as ThreeObject3D,
  type Texture,
} from "three";
import { clone as cloneSkeleton } from "three/examples/jsm/utils/SkeletonUtils.js";
import type { RuntimePose } from "../store/editorStore";
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
  pose,
  selected,
  editMode,
  transformMode,
  snap,
  onSelect,
  onTransform,
  children,
}: {
  node: MeshNode | ObjectNode | PrimitiveNode;
  pose?: RuntimePose;
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
  const position = (pose?.position ?? node.position) as [number, number, number];
  const rotation = (pose?.rotation ?? node.rotation) as [number, number, number];
  const scale = (pose?.scale ?? node.scale) as [number, number, number];

  useEffect(() => {
    setReady(Boolean(group.current));
  }, [node.id, selected, editMode]);

  return (
    <>
      <group
        ref={group}
        position={position}
        rotation={rotation}
        scale={scale}
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
  castShadow = true,
}: {
  node: MeshNode;
  animationState?: "idle" | "move" | "run" | "jump" | "attack" | "hit" | "death";
  castShadow?: boolean;
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
      // KayKit characters ship with sheathed/offhand sword sockets — keep the main blade visible.
      if (child.name === "1H_Sword" || child.name.includes("1H_Sword")) {
        child.visible = !child.name.includes("Offhand");
      }
      const mesh = child as Mesh;
      if (!mesh.isMesh) return;
      mesh.castShadow = castShadow;
      mesh.receiveShadow = true;
      const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
      materials.forEach((material) => {
        if (!material) return;
        // Keep intentional glass/water alpha; force solid props fully opaque.
        if ((material.opacity ?? 1) >= 0.99) {
          material.transparent = false;
          material.opacity = 1;
          material.depthWrite = true;
          material.needsUpdate = true;
        }
      });
    });
  }, [castShadow, cloned]);

  useEffect(() => {
    if (!clipName) return;
    const action = actions[clipName];
    if (!action) return;
    const fade = animation?.fadeSeconds ?? 0.18;
    const oneShot =
      animation?.loop === false ||
      animationState === "attack" ||
      animationState === "hit" ||
      animationState === "death";
    action.reset();
    action.setLoop(oneShot ? LoopOnce : LoopRepeat, oneShot ? 1 : Infinity);
    if (oneShot) action.clampWhenFinished = true;
    action.fadeIn(fade).play();
    return () => {
      action.fadeOut(fade);
    };
  }, [actions, animation?.fadeSeconds, animation?.loop, animationState, clipName]);

  return <primitive object={cloned} />;
}

function hasIncludedAncestor(node: ThreeObject3D, includeNodes: string[]): boolean {
  let cursor: ThreeObject3D | null = node;
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

export function preloadSceneAssets(meshes: MeshNode[], worldSource?: string | null) {
  const urls = new Set<string>();
  meshes.forEach((mesh) => {
    if (/\.gl(b|tf)(\?|$)/i.test(mesh.source) || mesh.format === "glb" || mesh.format === "gltf") {
      urls.add(assetUrl(mesh.source));
    }
  });
  if (worldSource && /\.gl(b|tf)(\?|$)/i.test(worldSource)) {
    urls.add(assetUrl(worldSource));
  }
  urls.forEach((url) => useGLTF.preload(url));
}

function isStaticInstanceCandidate(mesh: MeshNode): boolean {
  if (!mesh.visible) return false;
  if (mesh.meta?.animation || mesh.meta?.visualFor) return false;
  if (mesh.parentId) return false;
  const format = (mesh.format || "").toLowerCase();
  return (
    format === "glb" ||
    format === "gltf" ||
    /\.gl(b|tf)(\?|$)/i.test(mesh.source)
  );
}

function LodGlbVisual({
  node,
  castShadow,
}: {
  node: MeshNode;
  castShadow: boolean;
}) {
  const lod = node.meta?.lod;
  if (!Array.isArray(lod) || lod.length < 2) {
    return <GlbVisual node={node} castShadow={castShadow} />;
  }
  const levels = lod.filter((item): item is string => typeof item === "string");
  const distances = levels.map((_, index) => index * 12);
  return (
    <Detailed distances={distances}>
      {levels.map((source, index) => (
        <GlbVisual
          key={`${node.id}-lod-${index}`}
          node={{ ...node, source }}
          castShadow={castShadow && index === 0}
        />
      ))}
    </Detailed>
  );
}

function InstancedSourceGroup({
  source,
  meshes,
  runtimePoses,
}: {
  source: string;
  meshes: MeshNode[];
  runtimePoses: Record<string, RuntimePose>;
}) {
  const gltf = useGLTF(assetUrl(source));
  const meshRef = useRef<InstancedMesh>(null);
  const dummy = useMemo(() => new Object3D(), []);
  const prototypeMesh = useMemo((): Mesh | null => {
    const found: Mesh[] = [];
    gltf.scene.traverse((child) => {
      const candidate = child as Mesh;
      if (candidate.isMesh) found.push(candidate);
    });
    return found[0] ?? null;
  }, [gltf.scene]);

  useLayoutEffect(() => {
    const target = meshRef.current;
    if (!target || !prototypeMesh) return;
    meshes.forEach((mesh, index) => {
      const pose = runtimePoses[mesh.id];
      const position = pose?.position ?? mesh.position;
      const rotation = pose?.rotation ?? mesh.rotation;
      const scale = pose?.scale ?? mesh.scale;
      dummy.position.set(position[0], position[1], position[2]);
      dummy.rotation.set(rotation[0], rotation[1], rotation[2]);
      dummy.scale.set(scale[0], scale[1], scale[2]);
      dummy.updateMatrix();
      target.setMatrixAt(index, dummy.matrix);
    });
    target.instanceMatrix.needsUpdate = true;
    target.count = meshes.length;
  }, [dummy, meshes, prototypeMesh, runtimePoses]);

  if (!prototypeMesh) {
    return (
      <>
        {meshes.map((mesh) => (
          <group
            key={mesh.id}
            position={(runtimePoses[mesh.id]?.position ?? mesh.position) as [number, number, number]}
            rotation={(runtimePoses[mesh.id]?.rotation ?? mesh.rotation) as [number, number, number]}
            scale={(runtimePoses[mesh.id]?.scale ?? mesh.scale) as [number, number, number]}
          >
            <GlbVisual node={mesh} castShadow={false} />
          </group>
        ))}
      </>
    );
  }

  return (
    <instancedMesh
      ref={meshRef}
      args={[prototypeMesh.geometry, prototypeMesh.material, meshes.length]}
      castShadow={false}
      receiveShadow
      frustumCulled={false}
    />
  );
}

export function MeshAssets({
  meshes,
  objects,
  primitives = [],
  runtimePoses = {},
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
  runtimePoses?: Record<string, RuntimePose>;
  editMode: boolean;
  selectedId: string | null;
  transformMode: TransformMode;
  snap: SnapSettings;
  onSelect: (id: string) => void;
  onTransform: TransformCallback;
}) {
  const meshById = useMemo(() => new Map(meshes.map((mesh) => [mesh.id, mesh])), [meshes]);
  const objectById = useMemo(() => new Map(objects.map((object) => [object.id, object])), [objects]);
  const primitiveById = useMemo(
    () => new Map(primitives.map((primitive) => [primitive.id, primitive])),
    [primitives],
  );
  const { childrenByParent, rootIds, graphNodes } = useMemo(() => {
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
    const rootIds = graphNodes.filter((node) => !childIds.has(node.id)).map((node) => node.id);
    return { childrenByParent, rootIds, graphNodes };
  }, [meshes, objects, primitives]);
  const { instancedBySource, instancedIds } = useMemo(() => {
    const groups = new Map<string, MeshNode[]>();
    meshes.forEach((mesh) => {
      if (!isStaticInstanceCandidate(mesh)) return;
      const list = groups.get(mesh.source) ?? [];
      list.push(mesh);
      groups.set(mesh.source, list);
    });
    const instancedBySource = new Map<string, MeshNode[]>();
    const instancedIds = new Set<string>();
    groups.forEach((list, source) => {
      if (list.length < 3) return;
      instancedBySource.set(source, list);
      list.forEach((mesh) => instancedIds.add(mesh.id));
    });
    return { instancedBySource, instancedIds };
  }, [meshes]);

  const renderNode = (id: string, ancestors: ReadonlySet<string>): React.ReactNode => {
    if (ancestors.has(id) || instancedIds.has(id)) {
      return null;
    }
    const nextAncestors = new Set(ancestors).add(id);
    const object = objectById.get(id);
    if (object) {
      return (
        <TransformableGroup
          key={object.id}
          node={object}
          pose={runtimePoses[object.id]}
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
          pose={runtimePoses[primitive.id]}
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
          pose={runtimePoses[mesh.id]}
          selected={selectedId === mesh.id}
          editMode={editMode}
          transformMode={transformMode}
          snap={snap}
          onSelect={onSelect}
          onTransform={onTransform}
        >
          <LodGlbVisual node={mesh} castShadow={!editMode} />
        </TransformableGroup>
      </Suspense>
    );
  };
  const renderIds =
    rootIds.length > 0 ? rootIds : graphNodes.map((node) => node.id);

  return (
    <>
      {renderIds.map((id) => renderNode(id, new Set()))}
      {[...instancedBySource.entries()].map(([source, group]) => (
        <Suspense key={`instances:${source}`} fallback={null}>
          <InstancedSourceGroup source={source} meshes={group} runtimePoses={runtimePoses} />
        </Suspense>
      ))}
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
  const cloned = useMemo(() => gltf.scene.clone(true), [gltf.scene]);
  return (
    <primitive
      object={cloned}
      position={world.position as [number, number, number]}
      rotation={world.rotation as [number, number, number]}
      scale={world.scale as [number, number, number]}
    />
  );
}
