import { useCallback, useEffect, useRef, useState } from "react";
import { wsUrl } from "../config";
import type { RuntimePose } from "../store/editorStore";
import type {
  ConnectionState,
  RuntimeMode,
  ScenePayload,
} from "../types/scene";

type SocketEnvelope = {
  type?: unknown;
  mode?: unknown;
  scene?: unknown;
  snapshot?: unknown;
  frame?: unknown;
  transforms?: unknown;
  full?: unknown;
  protocol?: unknown;
  version?: unknown;
  capabilities?: unknown;
  revision?: unknown;
  event?: unknown;
};

export type TransformDelta = {
  id: string;
  position: number[];
  rotation: number[];
  scale: number[];
};

function isScenePayload(value: unknown): value is ScenePayload {
  if (!value || typeof value !== "object") {
    return false;
  }
  const scene = value as Partial<ScenePayload>;
  return (
    typeof scene.name === "string" &&
    typeof scene.background === "string" &&
    Array.isArray(scene.meshes) &&
    Array.isArray(scene.objects) &&
    Array.isArray(scene.annotations) &&
    Array.isArray(scene.trajectories)
  );
}

function parseTransforms(value: unknown): Record<string, RuntimePose> | null {
  if (!Array.isArray(value)) return null;
  const poses: Record<string, RuntimePose> = {};
  for (const item of value) {
    if (!item || typeof item !== "object") continue;
    const row = item as Partial<TransformDelta>;
    if (typeof row.id !== "string") continue;
    if (!Array.isArray(row.position) || !Array.isArray(row.rotation) || !Array.isArray(row.scale)) {
      continue;
    }
    poses[row.id] = {
      position: row.position as number[],
      rotation: row.rotation as number[],
      scale: row.scale as number[],
    };
  }
  return poses;
}

function isTextEntry(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  return (
    target.isContentEditable ||
    target instanceof HTMLInputElement ||
    target instanceof HTMLTextAreaElement ||
    target instanceof HTMLSelectElement
  );
}

export type ReplayControlAction = "start" | "stop" | "complete";

export function useSceneSocket(
  onScene: (scene: ScenePayload) => void,
  onResync?: () => void,
  onReplayControl?: (action: ReplayControlAction, payload: Record<string, unknown>) => void,
  onTransforms?: (poses: Record<string, RuntimePose>, replace: boolean) => void,
) {
  const socketRef = useRef<WebSocket | null>(null);
  const sceneHandlerRef = useRef(onScene);
  const transformsHandlerRef = useRef(onTransforms);
  const replayHandlerRef = useRef(onReplayControl);
  const modeRef = useRef<RuntimeMode>("edit");
  const revisionRef = useRef<number | null>(null);
  const replayingRef = useRef(false);
  const injectingReplayRef = useRef(false);
  const [connection, setConnection] =
    useState<ConnectionState>("connecting");
  const [mode, setMode] = useState<RuntimeMode>("edit");
  const [protocol, setProtocol] = useState({ version: 1, compatible: true, capabilities: [] as string[] });
  const [lastAck, setLastAck] = useState<string | null>(null);
  const [recording, setRecording] = useState(false);
  const [replaying, setReplaying] = useState(false);

  useEffect(() => {
    sceneHandlerRef.current = onScene;
  }, [onScene]);

  useEffect(() => {
    transformsHandlerRef.current = onTransforms;
  }, [onTransforms]);

  useEffect(() => {
    replayHandlerRef.current = onReplayControl;
  }, [onReplayControl]);

  const send = useCallback((payload: object) => {
    const socket = socketRef.current;
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(payload));
    }
  }, []);

  useEffect(() => {
    let disposed = false;
    let retryTimer: number | undefined;

    const connect = (path = "/ws") => {
      if (disposed) {
        return;
      }
      setConnection("connecting");
      const socket = new WebSocket(wsUrl(path));
      let opened = false;
      socketRef.current = socket;

      socket.addEventListener("open", () => {
        opened = true;
        if (!disposed) {
          setConnection("connected");
        }
      });

      socket.addEventListener("message", (event: MessageEvent<unknown>) => {
        if (typeof event.data !== "string") {
          return;
        }
        try {
          const data: unknown = JSON.parse(event.data);
          if (!data || typeof data !== "object") {
            return;
          }
          const envelope = data as SocketEnvelope;
          if (envelope.type === "hello") {
            const version = typeof envelope.version === "number" ? envelope.version : 1;
            const namedProtocol = typeof envelope.protocol === "string" ? envelope.protocol : null;
            const legacy = namedProtocol === null && version === 1;
            const hello = data as { recording?: unknown; replaying?: unknown };
            setRecording(hello.recording === true);
            setReplaying(hello.replaying === true);
            replayingRef.current = hello.replaying === true;
            setProtocol({
              version,
              compatible: legacy || (namedProtocol === "sceneify-realtime" && version === 2),
              capabilities: Array.isArray(envelope.capabilities)
                ? envelope.capabilities.filter((item): item is string => typeof item === "string")
                : [],
            });
          }
          if (envelope.type === "command_ack") {
            setLastAck(typeof (data as { commandId?: unknown }).commandId === "string"
              ? (data as { commandId: string }).commandId
              : null);
          }
          if (envelope.type === "capture_request") {
            window.dispatchEvent(
              new CustomEvent("sceneify-capture-request", {
                detail: data as Record<string, unknown>,
              }),
            );
            return;
          }
          if (envelope.type === "record_state" || envelope.type === "record_ack") {
            const state = data as { recording?: unknown };
            setRecording(state.recording === true);
          }
          if (envelope.type === "replay_control") {
            const control = data as { action?: unknown };
            const action = control.action;
            if (action === "start" || action === "stop" || action === "complete") {
              const active = action === "start";
              replayingRef.current = active;
              setReplaying(active);
              replayHandlerRef.current?.(action, data as Record<string, unknown>);
            }
          }
          if (envelope.type === "replay_input") {
            const input = data as {
              action?: unknown;
              value?: unknown;
              metadata?: { code?: unknown; repeat?: unknown };
            };
            if (input.action === "keydown" || input.action === "keyup") {
              const code =
                typeof input.metadata?.code === "string"
                  ? input.metadata.code
                  : typeof input.value === "string"
                    ? input.value
                    : "";
              const key = typeof input.value === "string" ? input.value : code;
              if (code || key) {
                injectingReplayRef.current = true;
                window.dispatchEvent(
                  new KeyboardEvent(input.action === "keydown" ? "keydown" : "keyup", {
                    key,
                    code: code || key,
                    bubbles: true,
                    cancelable: true,
                    repeat: input.metadata?.repeat === true,
                  }),
                );
                injectingReplayRef.current = false;
              }
            }
          }
          if (envelope.type === "resync") onResync?.();
          if (envelope.mode === "play" || envelope.mode === "edit") {
            modeRef.current = envelope.mode;
            setMode(envelope.mode);
          } else if (envelope.type === "frame") {
            modeRef.current = "play";
            setMode("play");
          } else if (envelope.type === "hello") {
            modeRef.current = "edit";
            setMode("edit");
          }

          if (envelope.type === "frame") {
            const poses = parseTransforms(envelope.transforms);
            if (poses) {
              const full = (data as { full?: unknown }).full === true;
              transformsHandlerRef.current?.(poses, full);
              return;
            }
            // Legacy full-scene frames: ignore in edit mode; apply only in play.
            if (modeRef.current !== "play") {
              return;
            }
          }

          const nextScene = isScenePayload(envelope.scene)
            ? envelope.scene
            : isScenePayload(envelope.snapshot)
              ? envelope.snapshot
            : envelope.type !== "frame" && isScenePayload(envelope.frame)
              ? envelope.frame
              : envelope.type !== "frame" && isScenePayload(data)
                ? data
                : null;
          if (nextScene) {
            const revision = typeof nextScene.revision === "number" ? nextScene.revision : null;
            if (
              revision !== null &&
              revisionRef.current !== null &&
              revision === revisionRef.current &&
              envelope.type !== "hello" &&
              envelope.type !== "snapshot"
            ) {
              return;
            }
            if (revision !== null) revisionRef.current = revision;
            sceneHandlerRef.current(nextScene);
          }
        } catch {
          return;
        }
      });

      socket.addEventListener("close", () => {
        if (socketRef.current === socket) {
          socketRef.current = null;
        }
        if (!disposed) {
          if (!opened && path === "/ws") {
            connect("/api/realtime");
          } else {
            setConnection("disconnected");
            modeRef.current = "edit";
            setMode("edit");
            retryTimer = window.setTimeout(() => connect(), 1500);
          }
        }
      });
    };

    connect();
    return () => {
      disposed = true;
      window.clearTimeout(retryTimer);
      socketRef.current?.close();
      socketRef.current = null;
    };
  }, [onResync]);

  useEffect(() => {
    const onCaptureResult = (event: Event) => {
      const detail = (event as CustomEvent<Record<string, unknown>>).detail;
      if (!detail || typeof detail !== "object") return;
      send({ type: "capture_result", ...detail });
    };
    window.addEventListener("sceneify-capture-result", onCaptureResult as EventListener);
    return () => {
      window.removeEventListener("sceneify-capture-result", onCaptureResult as EventListener);
    };
  }, [send]);

  useEffect(() => {
    const sendKey = (action: "down" | "up", event: KeyboardEvent) => {
      if (
        modeRef.current !== "play" ||
        isTextEntry(event.target) ||
        injectingReplayRef.current ||
        replayingRef.current
      ) {
        return;
      }
      send({
        type: "input",
        action: action === "down" ? "keydown" : "keyup",
        value: event.key,
        metadata: {
          code: event.code,
          repeat: event.repeat,
        },
      });
    };
    const onKeyDown = (event: KeyboardEvent) => sendKey("down", event);
    const onKeyUp = (event: KeyboardEvent) => sendKey("up", event);
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
    };
  }, [send]);

  const sendPointer = useCallback(
    (
      action: "move" | "down" | "up" | "wheel",
      event: React.PointerEvent<HTMLElement> | React.WheelEvent<HTMLElement>,
    ) => {
      if (modeRef.current !== "play") {
        return;
      }
      const bounds = event.currentTarget.getBoundingClientRect();
      const x = (event.clientX - bounds.left) / bounds.width;
      const y = (event.clientY - bounds.top) / bounds.height;
      send({
        type: "input",
        action: `pointer${action}`,
        value: [x, y],
        metadata: {
          button: "button" in event ? event.button : 0,
          buttons: "buttons" in event ? event.buttons : 0,
          deltaX: "deltaX" in event ? event.deltaX : 0,
          deltaY: "deltaY" in event ? event.deltaY : 0,
        },
      });
    },
    [send],
  );

  const sendSemanticEvent = useCallback(
    (name: string, nodeId?: string, data: Record<string, unknown> = {}) =>
      send({ type: "semantic_event", name, ...(nodeId ? { nodeId } : {}), data }),
    [send],
  );

  const startRecording = useCallback(
    (episodeId?: string) =>
      send({
        type: "record_control",
        action: "start",
        ...(episodeId ? { episodeId } : {}),
      }),
    [send],
  );

  const stopRecording = useCallback(
    () => send({ type: "record_control", action: "stop" }),
    [send],
  );

  return {
    connection,
    mode,
    protocol,
    lastAck,
    recording,
    replaying,
    sendPointer,
    sendSemanticEvent,
    startRecording,
    stopRecording,
  };
}
