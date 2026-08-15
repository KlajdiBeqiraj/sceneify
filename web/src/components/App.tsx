import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import {
  fetchScene,
  fetchSourceSync,
  importGlb,
  patchNode,
  RevisionConflict,
  savePythonScene,
  saveScene,
  sceneCommand,
  type NodePatch,
} from "../hooks/useScene";
import { useSceneSocket } from "../hooks/useSceneSocket";
import type { GameplayRole, ScenePayload } from "../types/scene";
import { gameplayRoles, primitiveById, runtimeConfig } from "../game/runtime";
import { editorReducer, initialEditorState, type RuntimePose } from "../store/editorStore";
import { AppShell } from "./AppShell";
import { IconRail } from "./IconRail";
import { TopToolbar } from "./TopToolbar";
import { Outliner } from "./Outliner";
import { CreatePalette } from "./CreatePalette";
import { AssetBrowser } from "./AssetBrowser";
import { Inspector } from "./Inspector";
import { Viewport } from "./Viewport";
import { GameOverlay } from "./GameOverlay";
import { StatusBar } from "./StatusBar";

function isTextEntry(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLElement &&
    (target.isContentEditable ||
      target instanceof HTMLInputElement ||
      target instanceof HTMLTextAreaElement ||
      target instanceof HTMLSelectElement)
  );
}

export function App() {
  const [state, dispatch] = useReducer(editorReducer, initialEditorState);
  const sceneRef = useRef<ScenePayload | null>(null);
  const revisionRef = useRef<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savePath, setSavePath] = useState("world.sceneify.json");
  const [pythonPath, setPythonPath] = useState("world.py");
  const [syncMode, setSyncMode] = useState<string>("json");
  const [status, setStatus] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [playing, setPlaying] = useState(false);

  const updateScene = useCallback((nextScene: ScenePayload) => {
    const revision = typeof nextScene.revision === "number" ? nextScene.revision : null;
    if (
      revision !== null &&
      revisionRef.current !== null &&
      revision === revisionRef.current &&
      sceneRef.current?.name === nextScene.name
    ) {
      return;
    }
    revisionRef.current = revision;
    sceneRef.current = nextScene;
    dispatch({ type: "scene", scene: nextScene });
    setError(null);
  }, []);

  const onTransforms = useCallback((poses: Record<string, RuntimePose>, replace: boolean) => {
    dispatch({ type: "runtimePoses", poses, replace });
  }, []);

  const reload = useCallback(async () => {
    try {
      revisionRef.current = null;
      updateScene(await fetchScene());
      setStatus("Scene synchronized");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load scene");
    }
  }, [updateScene]);

  const refreshSync = useCallback(async (path = pythonPath) => {
    try {
      const report = await fetchSourceSync(path);
      setSyncMode(report.mode);
    } catch {
      setSyncMode("json");
    }
  }, [pythonPath]);

  const onReplayControl = useCallback((action: "start" | "stop" | "complete") => {
    if (action === "start") {
      setPlaying(true);
      setStatus("Replaying episode");
      return;
    }
    if (action === "complete") {
      setStatus("Replay complete");
      return;
    }
    setStatus("Replay stopped");
  }, []);

  const {
    connection,
    mode: runtimeMode,
    protocol,
    sendSemanticEvent,
    recording,
    replaying,
  } = useSceneSocket(updateScene, reload, onReplayControl, onTransforms);
  const running = playing || runtimeMode === "play" || replaying;

  useEffect(() => {
    void reload();
  }, [reload]);

  useEffect(() => {
    void refreshSync();
  }, [refreshSync]);

  const run = useCallback(async (operation: () => Promise<{ scene: ScenePayload }>, message: string) => {
    setBusy(true);
    try {
      const result = await operation();
      revisionRef.current = null;
      updateScene(result.scene);
      setStatus(message);
    } catch (err) {
      if (err instanceof RevisionConflict) await reload();
      setStatus(err instanceof Error ? err.message : "Command failed");
    } finally {
      setBusy(false);
    }
  }, [reload, updateScene]);

  const command = useCallback((name: string, payload: Record<string, unknown> = {}, message = name) => {
    const scene = sceneRef.current;
    if (!scene) return;
    void run(() => sceneCommand(name, payload, scene.revision), message);
  }, [run]);
  const applyPatch = useCallback((id: string, patch: NodePatch) => {
    const scene = sceneRef.current;
    if (!scene) return;
    void run(() => patchNode(id, patch, scene.revision), `Updated ${id}`);
  }, [run]);

  const [focusNonce, setFocusNonce] = useState(0);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (isTextEntry(event.target) || running) {
        return;
      }
      const key = event.key.toLowerCase();
      const commandKey = event.ctrlKey || event.metaKey;
      if (commandKey && key === "z") {
        event.preventDefault();
        if (event.shiftKey) {
          command("redo", {}, "Redid command");
        } else {
          command("undo", {}, "Undid command");
        }
        return;
      }
      if (commandKey && key === "y") {
        event.preventDefault();
        command("redo", {}, "Redid command");
        return;
      }
      if (event.key === "Escape") {
        dispatch({ type: "select", id: null });
        return;
      }
      if (commandKey || event.altKey) {
        return;
      }
      if (event.key === "Delete" || event.key === "Backspace") {
        if (state.selectedId) {
          event.preventDefault();
          command("delete", { id: state.selectedId }, `Deleted ${state.selectedId}`);
        }
        return;
      }
      if (key === "f") {
        if (state.selectedId) {
          event.preventDefault();
          setFocusNonce((value) => value + 1);
        }
        return;
      }
      if (key === "w") {
        dispatch({ type: "transformMode", mode: "translate" });
      } else if (key === "e") {
        dispatch({ type: "transformMode", mode: "rotate" });
      } else if (key === "r") {
        dispatch({ type: "transformMode", mode: "scale" });
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [command, running, state.selectedId]);

  useEffect(() => {
    if (!running || state.gamePhase !== "playing") return;
    let previous = performance.now();
    const timer = window.setInterval(() => {
      const now = performance.now();
      dispatch({ type: "gameTick", delta: (now - previous) / 1000 });
      previous = now;
    }, 100);
    return () => window.clearInterval(timer);
  }, [running, state.gamePhase]);

  useEffect(() => {
    if (!replaying || !state.scene?.game || state.gamePhase === "playing") return;
    const spawn = primitiveById(state.scene, runtimeConfig(state.scene).playerNodeId)?.position as
      | [number, number, number]
      | undefined;
    dispatch({ type: "gameStart", timeLimit: runtimeConfig(state.scene).seconds, spawn });
  }, [replaying, state.gamePhase, state.scene]);

  async function onSave() {
    try {
      const saved = await saveScene(savePath, state.scene?.revision);
      setStatus(`Saved ${saved}`);
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Save failed");
    }
  }

  async function onSavePython() {
    try {
      const result = await savePythonScene(pythonPath, state.scene?.revision, "auto");
      setSyncMode(result.sync.mode);
      setStatus(`Saved Python ${result.saved} (${result.sync.mode})`);
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Python save failed");
    }
  }

  if (error) {
    return <div className="panel error">Could not load scene: {error}</div>;
  }

  if (!state.scene) {
    return <div className="loading-panel">Loading Sceneify</div>;
  }

  const scene = state.scene;
  const gameConfig = runtimeConfig(scene);
  const roles = gameplayRoles(scene);
  const editorConnected = connection === "connected" && protocol.compatible;
  const playerSpawn = primitiveById(scene, gameConfig.playerNodeId)?.position as [number, number, number] | undefined;
  const gameEvent = (event: GameplayRole, nodeId: string) => {
    if (state.gamePhase !== "playing") return;
    sendSemanticEvent(event, nodeId);
    if (event === "pickup") {
      const value = scene.game?.collectibles?.find((item) => item.nodeId === nodeId)?.value ?? 1;
      dispatch({ type: "gamePickup", id: nodeId, value });
      if (state.score + value >= gameConfig.requiredScore) setStatus("All relics collected. Find the exit.");
    } else if (event === "hazard") {
      if (nodeId.startsWith("enemy:")) {
        const amount = Number(nodeId.slice("enemy:".length)) || 1;
        dispatch({ type: "gameDamage", amount });
      } else {
        dispatch({ type: "gameLose" });
      }
    } else if (event === "checkpoint") {
      const node = primitiveById(scene, nodeId);
      if (node) dispatch({ type: "checkpoint", position: node.position as [number, number, number] });
    } else if (event === "goal" && state.score >= gameConfig.requiredScore) {
      dispatch({ type: "gameWin" });
    }
  };
  const left = state.leftPanel === "outliner" ? <Outliner scene={scene} selectedId={state.selectedId} onSelect={(id) => dispatch({ type: "select", id })} onReparent={(id, parentId) => command("reparent", { id, parentId }, `Reparented ${id}`)} onVisibility={(id, visible) => applyPatch(id, { visible })} /> :
    state.leftPanel === "create" ? <CreatePalette onCreate={(primitive) => command("create_primitive", { primitive }, `Created ${primitive}`)} /> :
      <AssetBrowser onImport={(file) => void run(() => importGlb(file, scene.revision), `Imported ${file.name}`)} onCreateFromAsset={(asset) => {
        const source = asset.path || asset.source;
        if (source) command("create_asset", { assetId: asset.id, source, format: asset.format }, `Added ${source}`);
      }} />;
  const togglePlay = () => {
    setPlaying((value) => !value);
    dispatch({ type: "gameReset" });
    dispatch({ type: "select", id: null });
  };

  return (
    <AppShell
      playing={running}
      leftOpen={state.leftOpen && !running}
      inspectorOpen={state.inspectorOpen && !running}
      toolbar={
        <TopToolbar
          sceneName={scene.name}
          revision={scene.revision}
          connection={connection}
          transformMode={state.transformMode}
          busy={busy}
          savePath={savePath}
          pythonPath={pythonPath}
          onSavePath={setSavePath}
          onPythonPath={(path) => {
            setPythonPath(path);
            void refreshSync(path);
          }}
          onTransformMode={(mode) => dispatch({ type: "transformMode", mode })}
          onUndo={() => command("undo", {}, "Undid command")}
          onRedo={() => command("redo", {}, "Redid command")}
          onSave={() => void onSave()}
          onSavePython={() => void onSavePython()}
          onReload={() => void reload()}
          onToggleLeft={() => dispatch({ type: "toggleLeft" })}
          onPlay={togglePlay}
        />
      }
      rail={<IconRail panel={state.leftPanel} playing={playing} onPanel={(panel) => dispatch({ type: "panel", panel })} onToggleInspector={() => dispatch({ type: "toggleInspector" })} onPlay={togglePlay} />}
      left={left}
      viewport={
        <>
          <Viewport
            scene={scene}
            runtimePoses={state.runtimePoses}
            selectedId={state.selectedId}
            focusNonce={focusNonce}
            editing={editorConnected && !running}
            playing={running}
            gameActive={state.gamePhase === "playing"}
            collectedIds={state.collectedIds}
            gameRun={state.gameRun}
            transformMode={state.transformMode}
            snap={state.snap}
            onSelect={(id) => dispatch({ type: "select", id })}
            onTransform={(id, position, rotation, scale) => applyPatch(id, { position, rotation, scale })}
            onGameEvent={gameEvent}
            onAnnotationEvent={(name, nodeId) => sendSemanticEvent(name, nodeId)}
          />
          {running && scene.game && (
            <GameOverlay
              phase={state.gamePhase}
              score={state.score}
              targetScore={gameConfig.requiredScore}
              health={state.health}
              maxHealth={state.maxHealth}
              timeLeft={state.timeLeft}
              title={gameConfig.title}
              showScore={scene.game.hud?.showScore !== false}
              showHealth={scene.game.hud?.showHealth !== false}
              showTimer={scene.game.hud?.showTimer !== false}
              showAttackHint={Boolean(scene.game.enemies?.types?.length)}
              description={scene.game.hud?.description}
              controlsHint={scene.game.hud?.controlsHint}
              onStart={() => {
                dispatch({ type: "gameStart", timeLimit: gameConfig.seconds, spawn: playerSpawn });
                sendSemanticEvent("game_started");
              }}
              onExit={runtimeMode === "edit" ? () => setPlaying(false) : undefined}
            />
          )}
          {running && !scene.game && scene.presentation?.title && (
            <div className="showcase-title">
              <span>Sceneify environment study</span>
              <h1>{scene.presentation.title}</h1>
              {scene.presentation.subtitle && <p>{scene.presentation.subtitle}</p>}
              <small>
                {scene.presentation.cameraTour?.autoplay
                  ? "Automatic camera tour · close framing · selective light dimming"
                  : "Drag to orbit · Scroll to explore"}
              </small>
            </div>
          )}
        </>
      }
      inspector={<Inspector scene={scene} selectedId={state.selectedId} gameplayRole={state.selectedId ? roles.get(state.selectedId) ?? "none" : "none"} onGameplayRole={(id, role) => command("set_gameplay_role", { id, role }, `Set ${id} role to ${role}`)} onClose={() => dispatch({ type: "toggleInspector" })} onPatch={applyPatch} onDuplicate={(id) => command("duplicate", { id }, `Duplicated ${id}`)} onDelete={(id) => command("delete", { id }, `Deleted ${id}`)} onSavePrefab={(id) => {
        const taken = new Set((scene.prefabs ?? []).map((prefab) => prefab.id));
        let prefabId = `${id}_prefab`;
        let index = 2;
        while (taken.has(prefabId)) {
          prefabId = `${id}_prefab_${index}`;
          index += 1;
        }
        command("define_prefab", { id: prefabId, fromNode: id }, `Saved prefab ${prefabId}`);
      }} />}
      status={
        <StatusBar
          status={`${recording ? "Recording · " : ""}${replaying ? "Replaying · " : ""}${status}`}
          protocol={protocol}
          revision={scene.revision}
          selectedId={state.selectedId}
          syncMode={syncMode}
        />
      }
    />
  );
}
