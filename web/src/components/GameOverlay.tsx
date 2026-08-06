import { Clock3, Heart, RotateCcw, Swords, Trophy } from "lucide-react";
import type { GamePhase } from "../types/scene";

export function GameOverlay({
  phase,
  score,
  targetScore,
  health,
  maxHealth,
  timeLeft,
  title,
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
  onStart: () => void;
  onExit?: () => void;
}) {
  if (phase === "playing") {
    return (
      <div className="game-hud" aria-live="polite">
        <div><Trophy /><span>Relics</span><strong>{score} / {targetScore}</strong></div>
        <div><Heart /><span>Health</span><strong>{health} / {maxHealth}</strong></div>
        <div><Clock3 /><span>Time</span><strong>{Math.ceil(timeLeft)}</strong></div>
        <p>Move: WASD · Jump: Space · Attack: J or click · Sword clears enemies</p>
      </div>
    );
  }
  const heading = phase === "won" ? "Escape complete" : phase === "lost" ? "Run failed" : title;
  const detail =
    phase === "won"
      ? `You escaped with ${score} relics.`
      : phase === "lost"
        ? "You fell in the pit or ran out of health."
        : "Collect the relics, fight enemies with your sword, avoid the pit, then reach the exit.";
  return (
    <div className="game-menu" role="dialog" aria-modal="true" aria-labelledby="game-title">
      <div>
        <span className="eyebrow">Third-person vertical slice</span>
        <h1 id="game-title">{heading}</h1>
        <p>{detail}</p>
        <p className="game-menu-tip"><Swords size={16} /> Enemies have health bars — chop them down before they chip yours.</p>
        <button className="primary-button large" autoFocus onClick={onStart}>
          {phase === "menu" ? "Start run" : <><RotateCcw />Restart</>}
        </button>
        {onExit && <button className="text-button" onClick={onExit}>Return to editor</button>}
      </div>
    </div>
  );
}
