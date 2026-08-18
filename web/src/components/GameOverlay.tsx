import { Clock3, Heart, RotateCcw, Swords, Trophy } from "lucide-react";
import type { GamePhase } from "../types/scene";

export type MatchMetric = {
  id: string;
  label: string;
  value: string;
};

export function GameOverlay({
  phase,
  score,
  targetScore,
  health,
  maxHealth,
  timeLeft,
  title,
  showScore = true,
  showHealth = true,
  showTimer = true,
  showAttackHint = false,
  description,
  controlsHint,
  metrics,
  winMessage,
  loseMessage,
  drawMessage,
  startLabel,
  onStart,
  onExit,
}: {
  phase: GamePhase;
  score: number;
  targetScore: number;
  health: number;
  maxHealth: number;
  timeLeft: number;
  title: string;
  showScore?: boolean;
  showHealth?: boolean;
  showTimer?: boolean;
  showAttackHint?: boolean;
  description?: string;
  controlsHint?: string;
  metrics?: MatchMetric[];
  winMessage?: string;
  loseMessage?: string;
  drawMessage?: string;
  startLabel?: string;
  onStart: () => void;
  onExit?: () => void;
}) {
  const resolvedMetrics = metrics ?? [
    ...(showScore ? [{ id: "score", label: "Relics", value: `${score} / ${targetScore}` }] : []),
    ...(showHealth ? [{ id: "health", label: "Health", value: `${health} / ${maxHealth}` }] : []),
    ...(showTimer ? [{ id: "timer", label: "Time", value: `${Math.ceil(timeLeft)}` }] : []),
  ];
  if (phase === "playing") {
    const controls = controlsHint ?? (showAttackHint
      ? "Move: WASD · Jump: Space · Attack: J or click"
      : "Move: WASD · Jump: Space");
    return (
      <div className="game-hud" aria-live="polite">
        {resolvedMetrics.map((metric) => (
          <div key={metric.id}>
            {metric.id === "score" ? <Trophy /> : metric.id === "health" ? <Heart /> : <Clock3 />}
            <span>{metric.label}</span>
            <strong>{metric.value}</strong>
          </div>
        ))}
        {controlsHint !== "" && <p>{controls}</p>}
      </div>
    );
  }
  const heading =
    phase === "won" ? (winMessage ?? "You win")
    : phase === "lost" ? (loseMessage ?? "You lose")
    : phase === "draw" ? (drawMessage ?? "Draw")
    : title;
  const detail =
    phase === "won"
      ? (winMessage ?? (showScore ? `You escaped with ${score} relics.` : "Match complete."))
      : phase === "lost"
        ? (loseMessage ?? "The run is over.")
        : phase === "draw"
          ? (drawMessage ?? "The match is a draw.")
        : description ?? (showAttackHint
          ? "Collect the relics, fight enemies with your sword, avoid the pit, then reach the exit."
          : controlsHint ?? "Walk around with WASD and Space to jump.");
  return (
    <div className="game-menu" role="dialog" aria-modal="true" aria-labelledby="game-title">
      <div>
        <span className="eyebrow">{showAttackHint ? "Third-person vertical slice" : "Sceneify play mode"}</span>
        <h1 id="game-title">{heading}</h1>
        <p>{detail}</p>
        {showAttackHint && !controlsHint && (
          <p className="game-menu-tip"><Swords size={16} /> Enemies have health bars — chop them down before they chip yours.</p>
        )}
        <button className="primary-button large" autoFocus onClick={onStart}>
          {phase === "menu" ? (startLabel ?? "Start run") : <><RotateCcw />Restart</>}
        </button>
        {onExit && <button className="text-button" onClick={onExit}>Return to editor</button>}
      </div>
    </div>
  );
}
