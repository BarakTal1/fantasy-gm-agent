const EXAMPLES = [
  "Who should I pick up this week?",
  "Is trading Haliburton for Sabonis fair?",
  "Any buy-low targets on the wire?",
  "Who should I start tonight?",
];
export function EmptyState({ onPick }: { onPick: (t: string) => void }) {
  return (
    <div className="empty">
      <h1>Your fantasy GM, electrified.</h1>
      <p>Waiver-wire radar, trade analysis, and buy-low targets — grounded in your league, powered by Lightning AI.</p>
      <div className="examples">
        {EXAMPLES.map((e) => (
          <button key={e} className="example" onClick={() => onPick(e)}>{e}</button>
        ))}
      </div>
    </div>
  );
}
