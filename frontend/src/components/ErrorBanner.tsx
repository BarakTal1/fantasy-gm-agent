export function ErrorBanner({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="banner" role="alert">
      {message} <button onClick={onRetry}>Retry</button>
    </div>
  );
}
