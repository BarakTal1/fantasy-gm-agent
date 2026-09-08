const EXAMPLES = [
  "Who should I pick up this week?",
  "Is trading Haliburton for Sabonis fair?",
  "Any buy-low targets on the wire?",
  "Who should I start tonight?",
];
export function EmptyState({ onPick }: { onPick: (t: string) => void }) {
  return (
    <div className="empty">
      <h1>Your fantasy GM, on call.</h1>
      <p>Ask about waivers, trades, streaming, and buy-low targets — grounded in your league.</p>
      <div className="examples">
        {EXAMPLES.map((e) => (
          <button key={e} className="example" onClick={() => onPick(e)}>{e}</button>
        ))}
      </div>
    </div>
  );
}
