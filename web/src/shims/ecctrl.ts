/**
 * Type-only shim for ecctrl@1.0.92 used by `tsc --noEmit`.
 * Vite resolves the real package from node_modules at bundle time (no tsconfig paths plugin).
 * Needed because the package d.ts re-exports EcctrlJoystick from .tsx sources that fail strict tsc.
 */
import type { RapierRigidBody, RigidBodyProps } from "@react-three/rapier";
import type { ForwardRefExoticComponent, ReactNode, RefAttributes } from "react";

export interface CustomEcctrlRigidBody extends RapierRigidBody {
  rotateCamera?: (x: number, y: number) => void;
  rotateCharacterOnY?: (rad: number) => void;
}

export interface EcctrlProps extends RigidBodyProps {
  children?: ReactNode;
  debug?: boolean;
  capsuleHalfHeight?: number;
  capsuleRadius?: number;
  floatHeight?: number;
  disableControl?: boolean;
  disableFollowCam?: boolean;
  maxVelLimit?: number;
  jumpVel?: number;
  sprintMult?: number;
  camInitDis?: number;
  camMaxDis?: number;
  camMinDis?: number;
  camTargetPos?: { x: number; y: number; z: number };
  camListenerTarget?: "document" | "domElement";
}

declare const Ecctrl: ForwardRefExoticComponent<
  EcctrlProps & RefAttributes<CustomEcctrlRigidBody>
>;

export default Ecctrl;
