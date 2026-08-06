import { Clock3, RotateCcw, Trophy } from "lucide-react";
import type { GamePhase } from "../types/scene";

export function GameOverlay({
  phase,
  score,
  targetScore,
  timeLeft,
  title,
  onStart,
  onExit,
}: {
  phase: GamePhase;
  score: number;
  targetScore: number;
  timeLeft: number;
  title: string;
  onStart: () => void;
  onExit?: () => void;
}) {
  if (phase === "playing") {
    return (
      <div className="game-hud" aria-live="polite">
        <div><Trophy /><span>Relics</span><strong>{score} / {targetScore}</strong></div>
        <div><Clock3 /><span>Time</span><strong>{Math.ceil(timeLeft)}</strong></div>
        <p>Move: WASD or arrows · Jump: Space · Interact: F</p>
      </div>
    );
  }
  const heading = phase === "won" ? "Escape complete" : phase === "lost" ? "Run failed" : title;
  const detail = phase === "won" ? `You escaped with ${score} relics.` : phase === "lost" ? "The world reset before you reached the goal." : "Collect the relics, avoid hazards, and reach the exit.";
  return (
    <div className="game-menu" role="dialog" aria-modal="true" aria-labelledby="game-title">
      <div><span className="eyebrow">Third-person vertical slice</span><h1 id="game-title">{heading}</h1><p>{detail}</p>
        <button className="primary-button large" autoFocus onClick={onStart}>{phase === "menu" ? "Start run" : <><RotateCcw />Restart</>}</button>
        {onExit && <button className="text-button" onClick={onExit}>Return to editor</button>}
      </div>
    </div>
  );
}
