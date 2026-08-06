import { Environment, Grid, OrbitControls } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import {
  BallCollider,
  CapsuleCollider,
  CuboidCollider,
  Physics,
  RigidBody,
  type RapierRigidBody,
} from "@react-three/rapier";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Euler, Matrix4, Quaternion, Vector3, type Group } from "three";
import type {
  AnnotationNode,
  GameplayRole,
  MeshNode,
  PrimitiveNode,
  ScenePayload,
  SnapSettings,
  TransformMode,
} from "../types/scene";
import { gameplayRoles, primitiveById, runtimeConfig } from "../game/runtime";
import { assetUrl } from "../hooks/useScene";
import { EnvironmentViz } from "./EnvironmentViz";
import { GlbVisual, MeshAssets, PrimitiveContent, WorldMeshView } from "./MeshAssets";
import { Annotations } from "./Annotations";
import { Trajectories } from "./Trajectories";

function resolveAnnotations(scene: ScenePayload): AnnotationNode[] {
  const nodes = new Map(
    [...scene.objects, ...scene.meshes, ...(scene.primitives ?? [])].map((node) => [
      node.id,
      node,
    ]),
  );
  const worldMatrix = (nodeId: string, seen = new Set<string>()): Matrix4 | null => {
    const node = nodes.get(nodeId);
    if (!node || seen.has(nodeId)) return null;
    const nextSeen = new Set(seen).add(nodeId);
    const local = new Matrix4().compose(
      new Vector3(...(node.position as [number, number, number])),
      new Quaternion().setFromEuler(
        new Euler(...(node.rotation as [number, number, number])),
      ),
      new Vector3(...(node.scale as [number, number, number])),
    );
    if (!node.parentId) return local;
    const parent = worldMatrix(node.parentId, nextSeen);
    return parent ? parent.multiply(local) : local;
  };
  return scene.annotations.map((annotation) => {
    if (!annotation.targetId) return annotation;
    const matrix = worldMatrix(annotation.targetId);
    if (!matrix) return annotation;
    const position = new Vector3().setFromMatrixPosition(matrix);
    const offset = annotation.offset ?? [0, 0, 0];
    position.add(new Vector3(...(offset as [number, number, number])));
    return { ...annotation, position: position.toArray() };
  });
}

function targetFocus(
  scene: ScenePayload,
  annotation: AnnotationNode,
): { center: Vector3; radius: number } {
  const targetId = annotation.targetId!;
  const nodes = new Map(
    [...scene.objects, ...scene.meshes, ...(scene.primitives ?? [])].map((node) => [
      node.id,
      node,
    ]),
  );
  const worldMatrix = (nodeId: string, seen = new Set<string>()): Matrix4 | null => {
    const node = nodes.get(nodeId);
    if (!node || seen.has(nodeId)) return null;
    const nextSeen = new Set(seen).add(nodeId);
    const local = new Matrix4().compose(
      new Vector3(...(node.position as [number, number, number])),
      new Quaternion().setFromEuler(
        new Euler(...(node.rotation as [number, number, number])),
      ),
      new Vector3(...(node.scale as [number, number, number])),
    );
    if (!node.parentId) return local;
    const parent = worldMatrix(node.parentId, nextSeen);
    return parent ? parent.multiply(local) : local;
  };
  const matrix = worldMatrix(targetId);
  const node = nodes.get(targetId);
  const position = matrix
    ? new Vector3().setFromMatrixPosition(matrix)
    : new Vector3(...((node?.position ?? [0, 0, 0]) as [number, number, number]));
  // Prefer the authored POI offset height so heavily scaled GLBs still frame tightly.
  const offsetY = Math.abs(annotation.offset?.[1] ?? 2);
  const radius = Math.min(5.8, Math.max(2.4, offsetY * 1.15));
  return {
    center: position.clone().add(new Vector3(0, offsetY * 0.42, 0)),
    radius,
  };
}

function Player({
  spawn,
  speed,
  jump,
  cameraDistance,
  cameraHeight,
  active,
  visual,
  onEvent,
}: {
  spawn: [number, number, number];
  speed: number;
  jump: number;
  cameraDistance: number;
  cameraHeight: number;
  active: boolean;
  visual?: MeshNode;
  onEvent: (name: string) => void;
}) {
  const body = useRef<RapierRigidBody>(null);
  const keys = useRef(new Set<string>());
  const groundContacts = useRef(0);
  const eventHandler = useRef(onEvent);
  const visualRoot = useRef<Group>(null);
  const [motion, setMotion] = useState<"idle" | "run" | "jump">("idle");
  const { camera, gl } = useThree();

  useEffect(() => {
    eventHandler.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    if (!active) keys.current.clear();
  }, [active]);

  useEffect(
    () => () => {
      delete gl.domElement.dataset.sceneifyPlayerPosition;
      delete gl.domElement.dataset.sceneifyPlayerAnimation;
      delete gl.domElement.dataset.sceneifyPlayerFacing;
    },
    [gl],
  );

  useEffect(() => {
    const down = (event: KeyboardEvent) => {
      if (!active) return;
      if (
        ["KeyW", "KeyA", "KeyS", "KeyD", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Space"].includes(
          event.code,
        )
      ) {
        event.preventDefault();
      }
      keys.current.add(event.code);
      if (event.code === "Space" && groundContacts.current > 0 && body.current) {
        const velocity = body.current.linvel();
        body.current.setLinvel({ x: velocity.x, y: jump, z: velocity.z }, true);
        groundContacts.current = 0;
        eventHandler.current("player_jump");
      }
      if (event.code === "KeyF") eventHandler.current("player_interact");
    };
    const up = (event: KeyboardEvent) => keys.current.delete(event.code);
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
    };
  }, [active, jump]);

  useFrame((_, delta) => {
    if (!active || !body.current) return;
    const x =
      Number(keys.current.has("KeyD") || keys.current.has("ArrowRight")) -
      Number(keys.current.has("KeyA") || keys.current.has("ArrowLeft"));
    const z =
      Number(keys.current.has("KeyS") || keys.current.has("ArrowDown")) -
      Number(keys.current.has("KeyW") || keys.current.has("ArrowUp"));
    const direction = new Vector3(x, 0, z).normalize().multiplyScalar(speed);
    const velocity = body.current.linvel();
    body.current.setLinvel({ x: direction.x, y: velocity.y, z: direction.z }, true);
    if (direction.lengthSq() > 0 && visualRoot.current) {
      // Yaw follows movement; mesh-authored rotation stays on the inner group.
      const target = Math.atan2(direction.x, direction.z);
      const current = visualRoot.current.rotation.y;
      const shortestArc = Math.atan2(Math.sin(target - current), Math.cos(target - current));
      visualRoot.current.rotation.y = current + shortestArc * Math.min(1, delta * 12);
      gl.domElement.dataset.sceneifyPlayerFacing = String(visualRoot.current.rotation.y);
    }
    const nextMotion =
      Math.abs(velocity.y) > 0.8 ? "jump" : direction.lengthSq() > 0 ? "run" : "idle";
    setMotion((current) => (current === nextMotion ? current : nextMotion));
    gl.domElement.dataset.sceneifyPlayerAnimation = nextMotion;
    const translation = body.current.translation();
    const position = new Vector3(translation.x, translation.y, translation.z);
    gl.domElement.dataset.sceneifyPlayerPosition = `${translation.x},${translation.y},${translation.z}`;
    camera.position.lerp(
      position.clone().add(new Vector3(0, cameraHeight, cameraDistance)),
      Math.min(1, delta * 7),
    );
    camera.lookAt(position.clone().add(new Vector3(0, 0.55, 0)));
  });

  return (
    <RigidBody
      ref={body}
      type="dynamic"
      position={spawn}
      colliders={false}
      enabledRotations={[false, false, false]}
      linearDamping={5}
      canSleep={false}
    >
      <CapsuleCollider
        args={[0.38, 0.32]}
        friction={0}
        onCollisionEnter={() => {
          groundContacts.current += 1;
        }}
        onCollisionExit={() => {
          groundContacts.current = Math.max(0, groundContacts.current - 1);
        }}
      />
      {visual ? (
        <group
          ref={visualRoot}
          position={visual.position as [number, number, number]}
          rotation={[0, Math.PI, 0]}
          scale={visual.scale as [number, number, number]}
        >
          <group rotation={visual.rotation as [number, number, number]}>
            <GlbVisual node={visual} animationState={motion === "run" ? "run" : motion} />
          </group>
        </group>
      ) : (
        <mesh castShadow>
          <capsuleGeometry args={[0.32, 0.76, 8, 16]} />
          <meshStandardMaterial color="#ffd166" />
        </mesh>
      )}
    </RigidBody>
  );
}

function PrimitiveCollider({
  node,
  sensor,
  onEnter,
}: {
  node: PrimitiveNode;
  sensor: boolean;
  onEnter?: () => void;
}) {
  const scale = node.scale ?? [1, 1, 1];
  const size = node.size ?? [1, 1, 1];
  const half: [number, number, number] = [
    ((size[0] ?? 1) * (scale[0] ?? 1)) / 2,
    ((node.primitive === "plane" ? 0.08 : (size[1] ?? 1)) * (scale[1] ?? 1)) / 2,
    ((size[2] ?? 1) * (scale[2] ?? 1)) / 2,
  ];
  const collider =
    node.physics?.collider ??
    (node.primitive === "sphere" ? "ball" : node.primitive === "capsule" ? "capsule" : "cuboid");
  const common = { sensor, onIntersectionEnter: onEnter };
  if (collider === "ball") {
    return (
      <BallCollider
        args={[(node.radius ?? 0.5) * Math.max(scale[0] ?? 1, scale[1] ?? 1, scale[2] ?? 1)]}
        {...common}
      />
    );
  }
  if (collider === "capsule") {
    return (
      <CapsuleCollider
        args={[
          ((node.height ?? 0.8) * (scale[1] ?? 1)) / 2,
          (node.radius ?? 0.35) * Math.max(scale[0] ?? 1, scale[2] ?? 1),
        ]}
        {...common}
      />
    );
  }
  return <CuboidCollider args={half} {...common} />;
}

function GameWorld({
  scene,
  active,
  collectedIds,
  runId,
  onGameEvent,
}: {
  scene: ScenePayload;
  active: boolean;
  collectedIds: string[];
  runId: number;
  onGameEvent: (event: GameplayRole, nodeId: string) => void;
}) {
  const primitives = scene.primitives ?? [];
  const roles = gameplayRoles(scene);
  const config = runtimeConfig(scene);
  const spawnNode = primitiveById(scene, config.playerNodeId);
  const spawn = (spawnNode?.position ?? [0, 1, 0]) as [number, number, number];
  const triggered = useRef(new Set<string>());
  const visualByTarget = new Map(
    scene.meshes
      .filter((mesh) => typeof mesh.meta?.visualFor === "string")
      .map((mesh) => [mesh.meta!.visualFor as string, mesh]),
  );
  useEffect(() => {
    triggered.current.clear();
  }, [runId]);
  const groundY = scene.environment?.ground?.y ?? 0;
  return (
    <Physics gravity={[0, -9.81, 0]} timeStep={1 / 60} paused={!active}>
      <RigidBody type="fixed" position={[0, groundY - 0.1, 0]} colliders={false}>
        <CuboidCollider args={[100, 0.1, 100]} friction={1} />
      </RigidBody>
      <Player
        key={runId}
        spawn={spawn}
        speed={config.moveSpeed}
        jump={config.jumpSpeed}
        cameraDistance={config.cameraDistance}
        cameraHeight={config.cameraHeight}
        active={active}
        visual={config.playerNodeId ? visualByTarget.get(config.playerNodeId) : undefined}
        onEvent={() => undefined}
      />
      {primitives
        .filter(
          (node) =>
            node.id !== config.playerNodeId && !collectedIds.includes(node.id) && node.visible,
        )
        .map((node) => {
          const role = roles.get(node.id) ?? "none";
          const sensor = role !== "none" || node.physics?.sensor === true;
          const visual = visualByTarget.get(node.id);
          return (
            <RigidBody
              key={`${runId}:${node.id}`}
              type={node.physics?.body === "dynamic" ? "dynamic" : "fixed"}
              position={node.position as [number, number, number]}
              rotation={node.rotation as [number, number, number]}
              colliders={false}
            >
              {visual ? (
                <group
                  position={visual.position as [number, number, number]}
                  rotation={visual.rotation as [number, number, number]}
                  scale={visual.scale as [number, number, number]}
                >
                  <GlbVisual node={visual} />
                </group>
              ) : node.meta?.renderPrimitive !== false ? (
                <PrimitiveContent node={{ ...node, position: [0, 0, 0] }} selected={false} />
              ) : null}
              <PrimitiveCollider
                node={node}
                sensor={sensor}
                onEnter={
                  role === "none"
                    ? undefined
                    : () => {
                        if (role === "pickup" && triggered.current.has(node.id)) return;
                        triggered.current.add(node.id);
                        onGameEvent(role, node.id);
                      }
                }
              />
            </RigidBody>
          );
        })}
    </Physics>
  );
}

function PoiFocusCamera({
  scene,
  annotation,
  active,
}: {
  scene: ScenePayload;
  annotation: AnnotationNode;
  active: boolean;
}) {
  const { camera, gl } = useThree();
  const startPos = useRef(new Vector3());
  const blend = useRef(0);
  const angle = useRef(0);
  const focusKey = useRef<string | null>(null);

  useEffect(() => {
    if (!active || !annotation.targetId) return;
    if (focusKey.current !== annotation.id) {
      startPos.current.copy(camera.position);
      blend.current = 0;
      angle.current = Math.atan2(
        camera.position.x - (annotation.position[0] ?? 0),
        camera.position.z - (annotation.position[2] ?? 0),
      );
      focusKey.current = annotation.id;
    }
    gl.domElement.dataset.sceneifyPoiFocus = annotation.id;
    return () => {
      if (gl.domElement.dataset.sceneifyPoiFocus === annotation.id) {
        delete gl.domElement.dataset.sceneifyPoiFocus;
      }
    };
  }, [active, annotation, camera.position, gl]);

  useFrame((_, delta) => {
    if (!active || !annotation.targetId) return;
    const { center, radius } = targetFocus(scene, annotation);
    const orbitRadius = Math.max(3.2, radius * 2.1);
    const orbitHeight = Math.max(1.2, radius * 0.72);
    blend.current = Math.min(1, blend.current + delta * 0.9);
    const eased = 1 - (1 - blend.current) ** 3;
    if (blend.current >= 1) {
      angle.current += delta * 0.22;
    }
    const desired = new Vector3(
      center.x + Math.sin(angle.current) * orbitRadius,
      center.y + orbitHeight,
      center.z + Math.cos(angle.current) * orbitRadius,
    );
    camera.position.lerpVectors(startPos.current, desired, eased);
    if (blend.current >= 1) {
      camera.position.lerp(desired, 1 - Math.exp(-delta * 3.2));
    }
    camera.lookAt(center);
  });

  return null;
}

export function Viewport({
  scene,
  selectedId,
  editing,
  playing,
  gameActive,
  collectedIds,
  gameRun,
  transformMode,
  snap,
  onSelect,
  onTransform,
  onGameEvent,
  onAnnotationEvent,
}: {
  scene: ScenePayload;
  selectedId: string | null;
  editing: boolean;
  playing: boolean;
  gameActive: boolean;
  collectedIds: string[];
  gameRun: number;
  transformMode: TransformMode;
  snap: SnapSettings;
  onSelect: (id: string | null) => void;
  onTransform: (id: string, position: number[], rotation: number[], scale: number[]) => void;
  onGameEvent: (event: GameplayRole, nodeId: string) => void;
  onAnnotationEvent?: (name: string, nodeId: string) => void;
}) {
  const primitives = useMemo(() => scene.primitives ?? [], [scene.primitives]);
  const gamePlaying = playing && Boolean(scene.game);
  const presentation = scene.presentation ?? {};
  const camera = presentation.camera;
  const annotations = useMemo(() => resolveAnnotations(scene), [scene]);
  const [focusedPoiId, setFocusedPoiId] = useState<string | null>(null);
  const focusedAnnotation = annotations.find((item) => item.id === focusedPoiId) ?? null;
  const poiFocusActive = Boolean(focusedAnnotation?.targetId) && !editing && !gamePlaying;

  useEffect(() => {
    if (editing || gamePlaying) setFocusedPoiId(null);
  }, [editing, gamePlaying]);

  return (
    <Canvas
      shadows={presentation.shadows ?? true}
      camera={{ position: camera?.position ?? [5, 4, 7], fov: camera?.fov ?? 48 }}
      onCreated={({ gl }) => {
        gl.toneMappingExposure = presentation.exposure ?? 1;
      }}
      onPointerMissed={() => editing && onSelect(null)}
    >
      <color attach="background" args={[scene.background || "#10131a"]} />
      {presentation.fog && (
        <fog
          attach="fog"
          args={[
            presentation.fog.color ?? scene.background,
            presentation.fog.near ?? 12,
            presentation.fog.far ?? 55,
          ]}
        />
      )}
      <ambientLight intensity={presentation.environmentMap ? 0.42 : 0.78} />
      <hemisphereLight args={["#f0e6d8", "#3a4558", 0.55]} />
      <directionalLight castShadow position={[6, 10, 4]} intensity={1.55} shadow-mapSize={[2048, 2048]} />
      <directionalLight position={[-5, 6, -3]} intensity={0.35} />
      <Suspense fallback={null}>
        {presentation.environmentMap ? (
          <Environment files={assetUrl(presentation.environmentMap)} />
        ) : (
          <Environment preset={presentation.environmentPreset ?? "city"} />
        )}
      </Suspense>
      {presentation.grid !== false && (
        <Grid infiniteGrid fadeDistance={35} sectionColor="#35405b" cellColor="#202737" />
      )}
      {presentation.helpers !== false && <EnvironmentViz environment={scene.environment} />}
      {scene.environment?.worldMesh && <WorldMeshView world={scene.environment.worldMesh} />}
      {!gamePlaying && (
        <MeshAssets
          meshes={scene.meshes}
          objects={scene.objects}
          primitives={primitives}
          editMode={editing}
          selectedId={selectedId}
          transformMode={transformMode}
          snap={snap}
          onSelect={onSelect}
          onTransform={onTransform}
        />
      )}
      {!gamePlaying && (
        <Annotations
          items={annotations}
          focusedId={focusedPoiId}
          editing={editing}
          onFocusChange={setFocusedPoiId}
          onSemanticEvent={onAnnotationEvent}
        />
      )}
      {!gamePlaying && poiFocusActive && focusedAnnotation && (
        <PoiFocusCamera scene={scene} annotation={focusedAnnotation} active />
      )}
      {!gamePlaying && <Trajectories items={scene.trajectories} />}
      {gamePlaying && (
        <GameWorld
          scene={scene}
          active={gameActive}
          collectedIds={collectedIds}
          runId={gameRun}
          onGameEvent={onGameEvent}
        />
      )}
      {gamePlaying && (
        <MeshAssets
          meshes={scene.meshes.filter((mesh) => !mesh.meta?.visualFor)}
          objects={scene.objects}
          editMode={false}
          selectedId={null}
          transformMode={transformMode}
          snap={snap}
          onSelect={() => undefined}
          onTransform={() => undefined}
        />
      )}
      {!gamePlaying && !poiFocusActive && (
        <OrbitControls makeDefault target={camera?.target} />
      )}
    </Canvas>
  );
}
