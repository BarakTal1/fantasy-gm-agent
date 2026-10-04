// Yahoo's API terms require this attribution with links to Yahoo Fantasy and the
// unmodified logo (no inversion, recoloring or combining with other brands).
export function YahooAttribution() {
  return (
    <p className="yahoo-attribution">
      <span>Fantasy data provided by </span>
      <a href="https://sports.yahoo.com/fantasy/" target="_blank" rel="noopener noreferrer">
        <img className="yahoo-logo" src="/yahoo-fantasy-logo.png" alt="Yahoo Fantasy" />
      </a>
    </p>
  );
}
