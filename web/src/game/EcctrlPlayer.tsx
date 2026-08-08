import { KeyboardControls } from "@react-three/drei";
import { useFrame, useThree } from "@react-three/fiber";
import Ecctrl, { type CustomEcctrlRigidBody } from "ecctrl";
import { useEffect, useRef, useState } from "react";
import { Euler, Quaternion, type Group } from "three";
import type { MeshNode } from "../types/scene";
import { GlbVisual } from "../components/MeshAssets";

const KEYBOARD_MAP = [
  { name: "forward", keys: ["ArrowUp", "KeyW"] },
  { name: "backward", keys: ["ArrowDown", "KeyS"] },
  { name: "leftward", keys: ["ArrowLeft", "KeyA"] },
  { name: "rightward", keys: ["ArrowRight", "KeyD"] },
  { name: "jump", keys: ["Space"] },
  { name: "run", keys: ["ShiftLeft", "ShiftRight"] },
];

type EcctrlPlayerProps = {
  spawn: [number, number, number];
  speed: number;
  jump: number;
  sprintMult: number;
  cameraDistance: number;
  cameraHeight: number;
  active: boolean;
  visual?: MeshNode;
  onEvent: (name: string) => void;
};

/**
 * Browser player driven by ecctrl (camera-relative movement + follow cam).
 * Publishes the same DOM dataset hooks used by the simple controller / enemies.
 */
export function EcctrlPlayer({
  spawn,
  speed,
  jump,
  sprintMult,
  cameraDistance,
  cameraHeight,
  active,
  visual,
  onEvent,
}: EcctrlPlayerProps) {
  const body = useRef<CustomEcctrlRigidBody>(null);
  const visualRoot = useRef<Group>(null);
  const eventHandler = useRef(onEvent);
  const attackTimer = useRef(0);
  const attackCooldown = useRef(0);
  const swingLatched = useRef(false);
  const swingId = useRef(0);
  const [motion, setMotion] = useState<"idle" | "run" | "jump" | "attack">("idle");
  const { gl } = useThree();
  const camDistance = -Math.max(1.2, Math.abs(cameraDistance));

  useEffect(() => {
    eventHandler.current = onEvent;
  }, [onEvent]);

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
      if (event.code === "KeyJ") {
        event.preventDefault();
        tryAttack();
      }
      if (event.code === "KeyF") eventHandler.current("player_interact");
    };
    const pointerDown = (event: PointerEvent) => {
      if (!active || event.button !== 0) return;
      const target = event.target as HTMLElement | null;
      if (target?.closest("button, a, input, textarea, [role='dialog']")) return;
      tryAttack();
    };
    window.addEventListener("keydown", down);
    window.addEventListener("pointerdown", pointerDown);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("pointerdown", pointerDown);
    };
  }, [active, gl]);

  useFrame((_, delta) => {
    if (!body.current) return;
    attackCooldown.current = Math.max(0, attackCooldown.current - delta);
    if (attackTimer.current > 0) {
      attackTimer.current = Math.max(0, attackTimer.current - delta);
      if (!swingLatched.current && attackTimer.current <= 0.38 && attackTimer.current >= 0.18) {
        swingLatched.current = true;
        swingId.current += 1;
        gl.domElement.dataset.sceneifyAttackSwing = String(swingId.current);
      }
      if (attackTimer.current === 0) {
        delete gl.domElement.dataset.sceneifyPlayerAttacking;
      }
    }

    const translation = body.current.translation();
    const velocity = body.current.linvel();
    const rotation = body.current.rotation();
    const yaw = new Euler().setFromQuaternion(
      new Quaternion(rotation.x, rotation.y, rotation.z, rotation.w),
      "YXZ",
    ).y;
    gl.domElement.dataset.sceneifyPlayerPosition = `${translation.x},${translation.y},${translation.z}`;
    gl.domElement.dataset.sceneifyPlayerFacing = String(yaw);

    const attacking = attackTimer.current > 0;
    const horizontal = Math.hypot(velocity.x, velocity.z);
    const nextMotion: "idle" | "run" | "jump" | "attack" = attacking
      ? "attack"
      : Math.abs(velocity.y) > 0.8
        ? "jump"
        : horizontal > 0.35
          ? "run"
          : "idle";
    setMotion((current) => (current === nextMotion ? current : nextMotion));
    gl.domElement.dataset.sceneifyPlayerAnimation = nextMotion;
  });

  return (
    <KeyboardControls map={KEYBOARD_MAP}>
      <Ecctrl
        ref={body}
        position={spawn}
        debug={false}
        disableControl={!active}
        disableFollowCam={!active}
        maxVelLimit={speed}
        jumpVel={jump}
        sprintMult={sprintMult}
        camInitDis={camDistance}
        camMaxDis={camDistance - 2}
        camMinDis={-1.2}
        camTargetPos={{ x: 0, y: Math.max(0.2, cameraHeight * 0.15), z: 0 }}
        camListenerTarget="domElement"
        capsuleHalfHeight={0.4}
        capsuleRadius={0.3}
        floatHeight={0.12}
        userData={{ role: "player" }}
      >
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
      </Ecctrl>
    </KeyboardControls>
  );
}
