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
import { Euler, Matrix4, Quaternion, Vector3, type Group, type PerspectiveCamera } from "three";
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
  const attackTimer = useRef(0);
  const attackCooldown = useRef(0);
  const swingLatched = useRef(false);
  const swingId = useRef(0);
  const [motion, setMotion] = useState<"idle" | "run" | "jump" | "attack">("idle");
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
      delete gl.domElement.dataset.sceneifyAttackSwing;
      delete gl.domElement.dataset.sceneifyPlayerAttacking;
    },
    [gl],
  );

  useEffect(() => {
    const tryAttack = () => {
      if (!active || attackTimer.current > 0 || attackCooldown.current > 0) return;
      attackTimer.current = 0.55;
      attackCooldown.current = 0.7;
      swingLatched.current = false;
      setMotion("attack");
      gl.domElement.dataset.sceneifyPlayerAttacking = "1";
      gl.domElement.dataset.sceneifyPlayerAnimation = "attack";
      eventHandler.current("player_attack");
    };
    const down = (event: KeyboardEvent) => {
      if (!active) return;
      if (
        [
          "KeyW",
          "KeyA",
          "KeyS",
          "KeyD",
          "ArrowUp",
          "ArrowDown",
          "ArrowLeft",
          "ArrowRight",
          "Space",
          "KeyJ",
        ].includes(event.code)
      ) {
        event.preventDefault();
      }
      keys.current.add(event.code);
      if (event.code === "Space" && groundContacts.current > 0 && body.current && attackTimer.current <= 0) {
        const velocity = body.current.linvel();
        body.current.setLinvel({ x: velocity.x, y: jump, z: velocity.z }, true);
        groundContacts.current = 0;
        eventHandler.current("player_jump");
      }
      if (event.code === "KeyJ") tryAttack();
      if (event.code === "KeyF") eventHandler.current("player_interact");
    };
    const up = (event: KeyboardEvent) => keys.current.delete(event.code);
    const pointerDown = (event: PointerEvent) => {
      if (!active || event.button !== 0) return;
      // Ignore UI clicks; only attack when the canvas (or game view) is the target.
      const target = event.target as HTMLElement | null;
      if (target?.closest("button, a, input, textarea, [role='dialog']")) return;
      tryAttack();
    };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    window.addEventListener("pointerdown", pointerDown);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
      window.removeEventListener("pointerdown", pointerDown);
    };
  }, [active, gl, jump]);

  useFrame((_, delta) => {
    if (!active || !body.current) return;
    attackCooldown.current = Math.max(0, attackCooldown.current - delta);
    if (attackTimer.current > 0) {
      attackTimer.current = Math.max(0, attackTimer.current - delta);
      // Mid-swing hit window for sword reach.
      if (!swingLatched.current && attackTimer.current <= 0.38 && attackTimer.current >= 0.18) {
        swingLatched.current = true;
        swingId.current += 1;
        gl.domElement.dataset.sceneifyAttackSwing = String(swingId.current);
      }
      if (attackTimer.current === 0) {
        delete gl.domElement.dataset.sceneifyPlayerAttacking;
      }
    }
    const attacking = attackTimer.current > 0;
    const x =
      Number(keys.current.has("KeyD") || keys.current.has("ArrowRight")) -
      Number(keys.current.has("KeyA") || keys.current.has("ArrowLeft"));
    const z =
      Number(keys.current.has("KeyS") || keys.current.has("ArrowDown")) -
      Number(keys.current.has("KeyW") || keys.current.has("ArrowUp"));
    const moveSpeed = attacking ? speed * 0.35 : speed;
    const direction = new Vector3(x, 0, z).normalize().multiplyScalar(moveSpeed);
    const velocity = body.current.linvel();
    body.current.setLinvel({ x: direction.x, y: velocity.y, z: direction.z }, true);
    if (direction.lengthSq() > 0 && visualRoot.current) {
      // Yaw follows movement; mesh-authored rotation stays on the inner group.
      const target = Math.atan2(direction.x, direction.z);
      const current = visualRoot.current.rotation.y;
      const shortestArc = Math.atan2(Math.sin(target - current), Math.cos(target - current));
      visualRoot.current.rotation.y = current + shortestArc * Math.min(1, delta * 12);
    }
    if (visualRoot.current) {
      gl.domElement.dataset.sceneifyPlayerFacing = String(visualRoot.current.rotation.y);
    }
    const nextMotion: "idle" | "run" | "jump" | "attack" = attacking
      ? "attack"
      : Math.abs(velocity.y) > 0.8
        ? "jump"
        : direction.lengthSq() > 0
          ? "run"
          : "idle";
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
      userData={{ role: "player" }}
    >
      <CapsuleCollider
        args={[0.4, 0.3]}
        friction={0.9}
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
  return <CuboidCollider args={half} friction={1.15} {...common} />;
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
  return (
    <Physics gravity={[0, -9.81, 0]} timeStep={1 / 60} paused={!active}>
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
      <EnemyWave
        scene={scene}
        active={active}
        runId={runId}
        onPlayerHit={(amount) => onGameEvent("hazard", `enemy:${amount}`)}
      />
      {primitives
        .filter(
          (node) =>
            node.id !== config.playerNodeId && !collectedIds.includes(node.id) && node.visible,
        )
        .map((node) => {
          const role = roles.get(node.id) ?? "none";
          const hasPhysics = Boolean(node.physics) || role !== "none";
          const sensor = role !== "none" || node.physics?.sensor === true;
          const visual = visualByTarget.get(node.id);
          const content = visual ? (
            <group
              position={visual.position as [number, number, number]}
              rotation={visual.rotation as [number, number, number]}
              scale={visual.scale as [number, number, number]}
            >
              <GlbVisual node={visual} />
            </group>
          ) : node.meta?.renderPrimitive !== false ? (
            <PrimitiveContent node={{ ...node, position: [0, 0, 0] }} selected={false} />
          ) : null;
          // Pure decorations (pads, pit visuals) render without inventing solid colliders.
          if (!hasPhysics) {
            return (
              <group
                key={`${runId}:${node.id}`}
                position={node.position as [number, number, number]}
                rotation={node.rotation as [number, number, number]}
              >
                {content}
              </group>
            );
          }
          return (
            <RigidBody
              key={`${runId}:${node.id}`}
              type={node.physics?.body === "dynamic" ? "dynamic" : "fixed"}
              position={node.position as [number, number, number]}
              rotation={node.rotation as [number, number, number]}
              colliders={false}
            >
              {content}
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

/** Pit hole in Collect & Escape — enemies must route around this AABB. */
const PIT_BOUNDS = { minX: -1.7, maxX: 5.7, minZ: -2.1, maxZ: 2.1 };
const PIT_FALL_Y = -1.2;

function segmentHitsPit(
  ax: number,
  az: number,
  bx: number,
  bz: number,
): boolean {
  const samples = 8;
  for (let i = 0; i <= samples; i += 1) {
    const t = i / samples;
    const x = ax + (bx - ax) * t;
    const z = az + (bz - az) * t;
    if (x > PIT_BOUNDS.minX && x < PIT_BOUNDS.maxX && z > PIT_BOUNDS.minZ && z < PIT_BOUNDS.maxZ) {
      return true;
    }
  }
  return false;
}

function chaseWaypoint(
  fromX: number,
  fromZ: number,
  toX: number,
  toZ: number,
): [number, number] {
  if (!segmentHitsPit(fromX, fromZ, toX, toZ)) return [toX, toZ];
  // Prefer the safe left lane; use the right rim only if already on that side.
  const leftLane = -6.2;
  const rightLane = 7.2;
  const preferLeft = fromX <= 2.5;
  const laneX = preferLeft ? leftLane : rightLane;
  const midZ = (PIT_BOUNDS.minZ + PIT_BOUNDS.maxZ) / 2;
  // Approach the lane beside the pit, then continue to the player.
  if (Math.abs(fromX - laneX) > 0.85) {
    return [laneX, fromZ];
  }
  if (fromZ > PIT_BOUNDS.maxZ + 0.4 && toZ < midZ) {
    return [laneX, PIT_BOUNDS.minZ - 0.8];
  }
  if (fromZ < PIT_BOUNDS.minZ - 0.4 && toZ > midZ) {
    return [laneX, PIT_BOUNDS.maxZ + 0.8];
  }
  return [laneX, toZ];
}

function EnemyActor({
  id,
  kind,
  source,
  spawn,
  speed,
  scale,
  health,
  contactDamage,
  animation,
  active,
  onPlayerHit,
  onDefeated,
}: {
  id: string;
  kind: string;
  source: string;
  spawn: [number, number, number];
  speed: number;
  scale: number;
  health: number;
  contactDamage: number;
  animation: { idle?: string; run?: string; hit?: string; death?: string };
  active: boolean;
  onPlayerHit: (amount: number) => void;
  onDefeated: (id: string) => void;
}) {
  const body = useRef<RapierRigidBody>(null);
  const visualRoot = useRef<Group>(null);
  const hp = useRef(health);
  const hitStun = useRef(0);
  const deathTimer = useRef(-1);
  const lastSwing = useRef("");
  const contactCooldown = useRef(0);
  const fellInPit = useRef(false);
  const [motion, setMotion] = useState<"idle" | "run" | "hit" | "death">("idle");
  const [hpRatio, setHpRatio] = useState(1);
  const { gl } = useThree();
  const visualNode = useMemo(
    () =>
      ({
        kind: "mesh" as const,
        id: `${id}_visual`,
        source,
        position: [0, -0.7, 0],
        rotation: [0, 0, 0],
        scale: [scale, scale, scale],
        visible: true,
        meta: {
          animation: {
            autoplay: animation.idle ?? "Idle",
            states: {
              idle: animation.idle ?? "Idle",
              run: animation.run ?? "Running_A",
              hit: animation.hit ?? "Hit_A",
              death: animation.death ?? "Death_A",
            },
            fadeSeconds: 0.1,
          },
        },
      }) satisfies MeshNode,
    [animation.death, animation.hit, animation.idle, animation.run, id, scale, source],
  );

  useFrame((_, delta) => {
    if (!active || !body.current) return;
    contactCooldown.current = Math.max(0, contactCooldown.current - delta);
    const translation = body.current.translation();
    // Fell into the open pit: despawn quietly (does not damage the player).
    if (!fellInPit.current && translation.y < PIT_FALL_Y) {
      fellInPit.current = true;
      setMotion("death");
      deathTimer.current = 0.35;
    }
    if (deathTimer.current >= 0) {
      deathTimer.current -= delta;
      body.current.setLinvel({ x: 0, y: body.current.linvel().y, z: 0 }, true);
      if (deathTimer.current <= 0) onDefeated(id);
      return;
    }
    if (hitStun.current > 0) {
      hitStun.current = Math.max(0, hitStun.current - delta);
      if (hitStun.current === 0) setMotion("idle");
    }

    const raw = gl.domElement.dataset.sceneifyPlayerPosition;
    const facingRaw = gl.domElement.dataset.sceneifyPlayerFacing;
    const swing = gl.domElement.dataset.sceneifyAttackSwing ?? "";
    if (raw && facingRaw && swing && swing !== lastSwing.current) {
      lastSwing.current = swing;
      const [px, , pz] = raw.split(",").map(Number);
      const toEnemy = new Vector3(translation.x - px, 0, translation.z - pz);
      const distance = toEnemy.length();
      if (distance > 0.2 && distance < 2.15) {
        const facing = Number(facingRaw);
        // Player visual root yaw: forward is roughly +Z after authored PI offset.
        const forward = new Vector3(Math.sin(facing), 0, Math.cos(facing)).normalize();
        const toward = toEnemy.normalize();
        if (forward.dot(toward) > 0.25) {
          hp.current = Math.max(0, hp.current - 1);
          setHpRatio(hp.current / health);
          gl.domElement.dataset.sceneifyEnemyHit = id;
          if (hp.current <= 0) {
            setMotion("death");
            deathTimer.current = 1.15;
            return;
          }
          setMotion("hit");
          hitStun.current = 0.35;
          // Horizontal knock only — vertical pops launched enemies onto props.
          const knock = toward.multiplyScalar(2.4);
          body.current.setLinvel({ x: knock.x, y: Math.min(0.2, body.current.linvel().y), z: knock.z }, true);
        }
      }
    }

    if (hitStun.current > 0 || deathTimer.current >= 0) return;
    if (!raw) return;
    const [px, , pz] = raw.split(",").map(Number);
    const [wx, wz] = chaseWaypoint(translation.x, translation.z, px, pz);
    const direction = new Vector3(wx - translation.x, 0, wz - translation.z);
    if (direction.lengthSq() < 0.04) {
      setMotion((current) => (current === "hit" || current === "death" ? current : "idle"));
      return;
    }
    direction.normalize();
    const velocity = body.current.linvel();
    // Preserve gravity; never invent upward chase velocity.
    body.current.setLinvel({ x: direction.x * speed, y: velocity.y, z: direction.z * speed }, true);
    if (visualRoot.current) {
      const target = Math.atan2(direction.x, direction.z);
      const current = visualRoot.current.rotation.y;
      const shortestArc = Math.atan2(Math.sin(target - current), Math.cos(target - current));
      visualRoot.current.rotation.y = current + shortestArc * Math.min(1, delta * 10);
    }
    setMotion((current) => (current === "hit" || current === "death" ? current : "run"));
  });

  return (
    <RigidBody
      ref={body}
      type="dynamic"
      position={spawn}
      colliders={false}
      enabledRotations={[false, false, false]}
      linearDamping={4}
      canSleep={false}
      userData={{ role: "enemy", kind, id }}
    >
      <CapsuleCollider
        args={[0.4, 0.3]}
        friction={0.95}
        onCollisionEnter={({ other }) => {
          if (other.rigidBodyObject?.userData?.role !== "player") return;
          if (deathTimer.current >= 0 || contactCooldown.current > 0) return;
          // Sword swing gives brief contact immunity so trading hits feels fair.
          if (gl.domElement.dataset.sceneifyPlayerAttacking === "1") return;
          contactCooldown.current = 0.9;
          onPlayerHit(contactDamage);
        }}
      />
      <group ref={visualRoot} rotation={[0, Math.PI, 0]}>
        <GlbVisual node={visualNode} animationState={motion} />
        <mesh position={[0, 1.35, 0]}>
          <planeGeometry args={[0.7, 0.08]} />
          <meshBasicMaterial color="#1c1520" transparent opacity={0.55} depthTest={false} />
        </mesh>
        <mesh position={[-(0.7 * (1 - hpRatio)) / 2, 1.35, 0.01]} scale={[hpRatio, 1, 1]}>
          <planeGeometry args={[0.66, 0.05]} />
          <meshBasicMaterial color="#ff6b6b" depthTest={false} />
        </mesh>
      </group>
    </RigidBody>
  );
}

function EnemyWave({
  scene,
  active,
  runId,
  onPlayerHit,
}: {
  scene: ScenePayload;
  active: boolean;
  runId: number;
  onPlayerHit: (amount: number) => void;
}) {
  const config = scene.game?.enemies;
  const types = config?.types ?? [];
  const spawnPoints = (config?.spawnPoints ?? []).filter((point) => point.length >= 3);
  type Actor = {
    id: string;
    kind: string;
    source: string;
    spawn: [number, number, number];
    speed: number;
    scale: number;
    health: number;
    contactDamage: number;
    animation: { idle?: string; run?: string; hit?: string; death?: string };
  };
  const [actors, setActors] = useState<Actor[]>([]);
  const actorsRef = useRef<Actor[]>([]);
  const timers = useRef<Record<string, number>>({});
  const spawnIndex = useRef(0);

  useEffect(() => {
    actorsRef.current = [];
    setActors([]);
    timers.current = {};
    spawnIndex.current = 0;
  }, [runId]);

  const removeActor = (id: string) => {
    const next = actorsRef.current.filter((actor) => actor.id !== id);
    actorsRef.current = next;
    setActors(next);
  };

  useFrame((_, delta) => {
    if (!active || types.length === 0 || spawnPoints.length === 0) return;
    const nextSpawns: Actor[] = [];
    types.forEach((type) => {
      const kind = type.kind;
      const alive =
        actorsRef.current.filter((actor) => actor.kind === kind).length +
        nextSpawns.filter((actor) => actor.kind === kind).length;
      const maxAlive = type.maxAlive ?? 2;
      const interval = type.intervalSeconds ?? 4.5;
      timers.current[kind] = (timers.current[kind] ?? 0.8) - delta;
      if (alive >= maxAlive || timers.current[kind] > 0) return;
      timers.current[kind] = interval;
      const point = spawnPoints[spawnIndex.current % spawnPoints.length]!;
      spawnIndex.current += 1;
      nextSpawns.push({
        id: `${kind}-${runId}-${Math.random().toString(36).slice(2, 8)}`,
        kind,
        source: type.source,
        spawn: [point[0]!, point[1]!, point[2]!],
        speed: type.speed ?? 2.6,
        scale: type.scale ?? 0.75,
        health: type.health ?? 3,
        contactDamage: type.contactDamage ?? 1,
        animation: type.animation ?? {
          idle: "Idle",
          run: "Running_A",
          hit: "Hit_A",
          death: "Death_A",
        },
      });
    });
    if (nextSpawns.length === 0) return;
    const merged = [...actorsRef.current, ...nextSpawns];
    actorsRef.current = merged;
    setActors(merged);
  });

  return (
    <>
      {actors.map((actor) => (
        <EnemyActor
          key={actor.id}
          {...actor}
          active={active}
          onPlayerHit={onPlayerHit}
          onDefeated={removeActor}
        />
      ))}
    </>
  );
}

type TourStop = NonNullable<NonNullable<ScenePayload["presentation"]>["cameraTour"]>["stops"] extends
  | Array<infer Stop>
  | undefined
  ? Stop
  : never;

function ForumCameraTour({
  scene,
  annotations,
  active,
  onStopChange,
  onSemanticEvent,
}: {
  scene: ScenePayload;
  annotations: AnnotationNode[];
  active: boolean;
  onStopChange: (stop: TourStop | null, annotation: AnnotationNode | null) => void;
  onSemanticEvent?: (name: string, nodeId: string) => void;
}) {
  const { camera, gl } = useThree();
  const stops = scene.presentation?.cameraTour?.stops ?? [];
  const loop = scene.presentation?.cameraTour?.loop !== false;
  const stopIndex = useRef(0);
  const phase = useRef<"travel" | "hold">("travel");
  const elapsed = useRef(0);
  const fromPos = useRef(new Vector3());
  const toPos = useRef(new Vector3());
  const fromTarget = useRef(new Vector3());
  const toTarget = useRef(new Vector3());
  const fromFov = useRef(scene.presentation?.camera?.fov ?? 40);
  const toFov = useRef(scene.presentation?.camera?.fov ?? 40);
  const reported = useRef<string | null>(null);
  const publishedStop = useRef<string | null>(null);
  const onStopChangeRef = useRef(onStopChange);
  const onSemanticRef = useRef(onSemanticEvent);
  const defaultFov = scene.presentation?.camera?.fov ?? 40;

  useEffect(() => {
    onStopChangeRef.current = onStopChange;
    onSemanticRef.current = onSemanticEvent;
  }, [onSemanticEvent, onStopChange]);

  useEffect(() => {
    if (!active || stops.length === 0) {
      onStopChangeRef.current(null, null);
      publishedStop.current = null;
      delete gl.domElement.dataset.sceneifyPoiFocus;
      delete gl.domElement.dataset.sceneifyTourStop;
      return;
    }
    const first = stops[0]!;
    stopIndex.current = 0;
    phase.current = "hold";
    elapsed.current = 0;
    fromPos.current.set(...(first.position as [number, number, number]));
    toPos.current.copy(fromPos.current);
    fromTarget.current.set(...(first.target as [number, number, number]));
    toTarget.current.copy(fromTarget.current);
    fromFov.current = first.fov ?? defaultFov;
    toFov.current = fromFov.current;
    camera.position.copy(fromPos.current);
    camera.lookAt(fromTarget.current);
    const perspective = camera as PerspectiveCamera;
    if (perspective.isPerspectiveCamera) {
      perspective.fov = fromFov.current;
      perspective.updateProjectionMatrix();
    }
    reported.current = null;
    publishedStop.current = null;
  }, [active, camera, defaultFov, gl, stops]);

  useFrame((_, delta) => {
    if (!active || stops.length === 0) return;
    const current = stops[stopIndex.current]!;
    const annotation = current.annotationId
      ? annotations.find((item) => item.id === current.annotationId) ?? null
      : null;
    if (publishedStop.current !== current.id) {
      publishedStop.current = current.id;
      onStopChangeRef.current(current, annotation);
    }
    gl.domElement.dataset.sceneifyTourStop = current.id;
    if (current.annotationId) {
      gl.domElement.dataset.sceneifyPoiFocus = current.annotationId;
    } else {
      delete gl.domElement.dataset.sceneifyPoiFocus;
    }
    const perspective = camera as PerspectiveCamera;

    if (phase.current === "travel") {
      const travel = Math.max(0.05, current.travel ?? 3.5);
      elapsed.current += delta;
      const t = Math.min(1, elapsed.current / travel);
      const eased = t * t * (3 - 2 * t);
      camera.position.lerpVectors(fromPos.current, toPos.current, eased);
      const look = new Vector3().lerpVectors(fromTarget.current, toTarget.current, eased);
      camera.lookAt(look);
      if (perspective.isPerspectiveCamera) {
        perspective.fov = fromFov.current + (toFov.current - fromFov.current) * eased;
        perspective.updateProjectionMatrix();
      }
      if (t < 1) return;
      phase.current = "hold";
      elapsed.current = 0;
      if (reported.current !== current.id) {
        reported.current = current.id;
        onSemanticRef.current?.("tour_stop", current.annotationId ?? current.id);
        if (current.annotationId) onSemanticRef.current?.("poi_selected", current.annotationId);
      }
      return;
    }

    camera.position.lerp(toPos.current, 1 - Math.exp(-delta * 4));
    camera.lookAt(toTarget.current);
    if (perspective.isPerspectiveCamera) {
      perspective.fov += (toFov.current - perspective.fov) * Math.min(1, delta * 4);
      perspective.updateProjectionMatrix();
    }
    const hold = Math.max(0.4, current.hold ?? 3);
    elapsed.current += delta;
    if (elapsed.current < hold) return;

    const nextIndex = stopIndex.current + 1;
    if (nextIndex >= stops.length) {
      if (!loop) return;
      stopIndex.current = 0;
    } else {
      stopIndex.current = nextIndex;
    }
    const next = stops[stopIndex.current]!;
    fromPos.current.copy(camera.position);
    toPos.current.set(...(next.position as [number, number, number]));
    fromTarget.current.copy(toTarget.current);
    toTarget.current.set(...(next.target as [number, number, number]));
    fromFov.current = perspective.isPerspectiveCamera ? perspective.fov : defaultFov;
    toFov.current = next.fov ?? defaultFov;
    phase.current = "travel";
    elapsed.current = 0;
    reported.current = null;
  });

  return null;
}

function SceneLights({
  presentation,
  lightScale,
  spotlightTarget,
  spotlightActive,
}: {
  presentation: NonNullable<ScenePayload["presentation"]>;
  lightScale: number;
  spotlightTarget: [number, number, number] | null;
  spotlightActive: boolean;
}) {
  const ambient = (presentation.ambientIntensity ?? (presentation.environmentMap ? 0.42 : 0.78)) * lightScale;
  const key = (presentation.keyLightIntensity ?? 1.45) * lightScale;
  return (
    <>
      <ambientLight intensity={ambient} />
      <hemisphereLight args={["#f0e6d8", "#3a4558", 0.55 * lightScale]} />
      <directionalLight
        castShadow
        position={[6, 10, 4]}
        intensity={key}
        shadow-mapSize={[2048, 2048]}
      />
      <directionalLight position={[-5, 6, -3]} intensity={0.35 * lightScale} />
      {spotlightActive && spotlightTarget && (
        <spotLight
          position={[spotlightTarget[0] + 1.4, spotlightTarget[1] + 3.2, spotlightTarget[2] + 1.8]}
          angle={0.38}
          penumbra={0.65}
          intensity={3.2}
          distance={16}
          castShadow
        >
          <object3D attach="target" position={spotlightTarget} />
        </spotLight>
      )}
    </>
  );
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
  const tourEnabled =
    !editing &&
    !gamePlaying &&
    Boolean(presentation.cameraTour?.autoplay && (presentation.cameraTour.stops?.length ?? 0) > 0);
  const [tourStop, setTourStop] = useState<TourStop | null>(null);
  const [tourAnnotation, setTourAnnotation] = useState<AnnotationNode | null>(null);
  const lightScale = tourStop?.lightScale ?? 1;
  const exposure = tourStop?.exposure ?? presentation.exposure ?? 1;
  const spotlightTarget = (tourStop?.target as [number, number, number] | undefined) ?? null;

  useEffect(() => {
    if (!tourEnabled) {
      setTourStop(null);
      setTourAnnotation(null);
    }
  }, [tourEnabled]);

  return (
    <>
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
        <ExposureController value={exposure} />
        <EnvironmentIntensityController value={Math.max(0.08, lightScale)} />
        <SceneLights
          presentation={presentation}
          lightScale={lightScale}
          spotlightTarget={spotlightTarget}
          spotlightActive={Boolean(tourStop?.spotlight)}
        />
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
            focusedId={tourAnnotation?.id ?? null}
            editing={editing}
            onFocusChange={() => undefined}
            onSemanticEvent={onAnnotationEvent}
          />
        )}
        {tourEnabled && (
          <ForumCameraTour
            scene={scene}
            annotations={annotations}
            active
            onStopChange={(stop, annotation) => {
              setTourStop(stop);
              setTourAnnotation(annotation);
            }}
            onSemanticEvent={onAnnotationEvent}
          />
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
        {!gamePlaying && !tourEnabled && (
          <OrbitControls makeDefault target={camera?.target} />
        )}
      </Canvas>
      {tourEnabled && tourAnnotation && (
        <aside className="poi-focus-panel" data-poi-focus-panel={tourAnnotation.id}>
          {tourAnnotation.meta?.category && <small>{tourAnnotation.meta.category}</small>}
          {tourAnnotation.label && <strong>{tourAnnotation.label}</strong>}
          {tourAnnotation.description && <span>{tourAnnotation.description}</span>}
          {tourStop?.cue && <em className="poi-tour-cue">{tourStop.cue}</em>}
        </aside>
      )}
      {tourEnabled && !tourAnnotation && tourStop?.cue && (
        <aside className="poi-focus-panel" data-poi-focus-panel={tourStop.id}>
          <small>Camera tour</small>
          <strong>{scene.presentation?.title ?? scene.name}</strong>
          <span>{tourStop.cue}</span>
        </aside>
      )}
    </>
  );
}

function ExposureController({ value }: { value: number }) {
  const { gl } = useThree();
  useFrame(() => {
    gl.toneMappingExposure += (value - gl.toneMappingExposure) * 0.08;
  });
  return null;
}

function EnvironmentIntensityController({ value }: { value: number }) {
  const { scene } = useThree();
  useFrame(() => {
    const current = scene.environmentIntensity ?? 1;
    scene.environmentIntensity = current + (value - current) * 0.1;
  });
  return null;
}
