import { useCallback, useEffect, useRef, useState } from "react";
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
  protocol?: unknown;
  version?: unknown;
  capabilities?: unknown;
  revision?: unknown;
  event?: unknown;
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

function socketUrl(path: string): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}${path}`;
}

export function useSceneSocket(
  onScene: (scene: ScenePayload) => void,
  onResync?: () => void,
) {
  const socketRef = useRef<WebSocket | null>(null);
  const sceneHandlerRef = useRef(onScene);
  const modeRef = useRef<RuntimeMode>("edit");
  const [connection, setConnection] =
    useState<ConnectionState>("connecting");
  const [mode, setMode] = useState<RuntimeMode>("edit");
  const [protocol, setProtocol] = useState({ version: 1, compatible: true, capabilities: [] as string[] });
  const [lastAck, setLastAck] = useState<string | null>(null);

  useEffect(() => {
    sceneHandlerRef.current = onScene;
  }, [onScene]);

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
      const socket = new WebSocket(socketUrl(path));
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
          const nextScene = isScenePayload(envelope.scene)
            ? envelope.scene
            : isScenePayload(envelope.snapshot)
              ? envelope.snapshot
            : isScenePayload(envelope.frame)
              ? envelope.frame
              : isScenePayload(data)
                ? data
                : null;
          if (nextScene) {
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
  }, []);

  useEffect(() => {
    const sendKey = (action: "down" | "up", event: KeyboardEvent) => {
      if (modeRef.current !== "play" || isTextEntry(event.target)) {
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

  return { connection, mode, protocol, lastAck, sendPointer, sendSemanticEvent };
}
