import { useState } from "react";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  const first = parts[0]?.[0] ?? "";
  const last = parts.length > 1 ? parts[parts.length - 1][0] : "";
  return (first + last).toUpperCase() || "?";
}

/** Player headshot with an initials-circle fallback (no url, or image error). */
export function PlayerAvatar({ name, image_url, size = 40 }:
  { name: string; image_url?: string | null; size?: number }) {
  const [failed, setFailed] = useState(false);
  const dim = { width: size, height: size };
  if (!image_url || failed) {
    return (
      <span className="avatar avatar-fallback" style={dim} aria-label={name} role="img">
        {initials(name)}
      </span>
    );
  }
  return (
    <img className="avatar" style={dim} src={image_url} alt={name}
         loading="lazy" onError={() => setFailed(true)} />
  );
}
