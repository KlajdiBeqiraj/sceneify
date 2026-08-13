import { useThree } from "@react-three/fiber";
import { useEffect } from "react";
import { Vector3 } from "three";

export type CaptureRequestDetail = {
  requestId?: unknown;
  preset?: unknown;
  nodeId?: unknown;
  width?: unknown;
  height?: unknown;
  eye?: unknown;
  target?: unknown;
  fov?: unknown;
};

function asVec3(value: unknown): [number, number, number] | null {
  if (!Array.isArray(value) || value.length !== 3) return null;
  if (!value.every((item) => typeof item === "number")) return null;
  return value as [number, number, number];
}

/**
 * Listens for window capture requests and replies with a PNG data URL + camera meta.
 */
export function CaptureBridge() {
  const { gl, scene, camera, size } = useThree();

  useEffect(() => {
    const onRequest = (event: Event) => {
      const detail = (event as CustomEvent<CaptureRequestDetail>).detail ?? {};
      const requestId = typeof detail.requestId === "string" ? detail.requestId : null;
      if (!requestId) return;

      const previous = {
        position: camera.position.clone(),
        quaternion: camera.quaternion.clone(),
        up: camera.up.clone(),
        fov: "fov" in camera && typeof camera.fov === "number" ? camera.fov : null,
        aspect: "aspect" in camera && typeof camera.aspect === "number" ? camera.aspect : null,
      };

      try {
        const preset = typeof detail.preset === "string" ? detail.preset : "presentation";
        const eye = asVec3(detail.eye);
        const target = asVec3(detail.target);
        const nodeId = typeof detail.nodeId === "string" ? detail.nodeId : null;
        const fov = typeof detail.fov === "number" ? detail.fov : null;

        let lookAt = target ?? ([0, 0, 0] as [number, number, number]);
        if (nodeId) {
          const object = scene.getObjectByName(nodeId);
          if (object) {
            const world = new Vector3();
            object.getWorldPosition(world);
            lookAt = [world.x, world.y, world.z];
          }
        }

        if (eye) {
          camera.position.set(...eye);
          camera.lookAt(...lookAt);
        } else if (preset === "topdown") {
          const span = 20;
          camera.position.set(lookAt[0], span, lookAt[2] + 0.01);
          camera.up.set(0, 0, -1);
          camera.lookAt(...lookAt);
        } else if (preset === "focus" && nodeId) {
          camera.position.set(lookAt[0] + 6, lookAt[1] + 4, lookAt[2] + 6);
          camera.lookAt(...lookAt);
        }

        if (fov !== null && "fov" in camera) {
          camera.fov = fov;
          camera.updateProjectionMatrix();
        }

        camera.updateMatrixWorld(true);
        gl.render(scene, camera);
        const dataUrl = gl.domElement.toDataURL("image/png");
        const comma = dataUrl.indexOf(",");
        const image = comma >= 0 ? dataUrl.slice(comma + 1) : dataUrl;

        window.dispatchEvent(
          new CustomEvent("sceneify-capture-result", {
            detail: {
              ok: true,
              requestId,
              mimeType: "image/png",
              image,
              width: size.width,
              height: size.height,
              preset,
              camera: {
                position: camera.position.toArray(),
                target: lookAt,
                fov: "fov" in camera ? camera.fov : null,
              },
            },
          }),
        );
      } catch (error) {
        window.dispatchEvent(
          new CustomEvent("sceneify-capture-result", {
            detail: {
              ok: false,
              requestId,
              error: error instanceof Error ? error.message : "Capture failed",
            },
          }),
        );
      } finally {
        camera.position.copy(previous.position);
        camera.quaternion.copy(previous.quaternion);
        camera.up.copy(previous.up);
        if (previous.fov !== null && "fov" in camera) {
          camera.fov = previous.fov;
          camera.updateProjectionMatrix();
        }
        gl.render(scene, camera);
      }
    };

    window.addEventListener("sceneify-capture-request", onRequest as EventListener);
    return () => {
      window.removeEventListener("sceneify-capture-request", onRequest as EventListener);
    };
  }, [camera, gl, scene, size.height, size.width]);

  return null;
}
