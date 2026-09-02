// useSong — given a song name, loads info.json plus the artifacts the visible
// lanes need, and exposes `{ status, data, error }` per artifact.
//
// `keys` lets a caller ask for only the artifacts it will render; `info` is
// always loaded. Re-runs when the song or the requested key set changes, and
// ignores results from a superseded song.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  artifactLoaders,
  type ArtifactData,
  type ArtifactKey,
  type LoadError,
} from "./loaders";

export type { ArtifactKey } from "./loaders";

export type ArtifactStatus = "idle" | "loading" | "ready" | "error";

export interface ArtifactState<K extends ArtifactKey> {
  status: ArtifactStatus;
  data: ArtifactData<K> | null;
  error: LoadError | null;
}

export type SongArtifacts = {
  [K in ArtifactKey]: ArtifactState<K>;
};

const ALL_KEYS = Object.keys(artifactLoaders) as ArtifactKey[];

type AnyState = { status: ArtifactStatus; data: unknown; error: LoadError | null };

function blankArtifacts(seed?: {
  keys: readonly ArtifactKey[];
  status: ArtifactStatus;
}): SongArtifacts {
  const out: Record<string, AnyState> = {};
  const loadingKeys = new Set<ArtifactKey>(seed?.keys ?? []);
  for (const key of ALL_KEYS) {
    out[key] =
      seed && loadingKeys.has(key)
        ? { status: seed.status, data: null, error: null }
        : { status: "idle", data: null, error: null };
  }
  return out as SongArtifacts;
}

export interface UseSongResult {
  song: string | null;
  /** true until every requested loader has settled */
  loading: boolean;
  artifacts: SongArtifacts;
  reload: () => void;
}

export function useSong(
  song: string | null,
  keys?: readonly ArtifactKey[],
): UseSongResult {
  const requested = useMemo<ArtifactKey[]>(() => {
    const set = new Set<ArtifactKey>(["info", ...(keys ?? ALL_KEYS)]);
    return ALL_KEYS.filter((k) => set.has(k));
  }, [keys]);

  const requestedSig = requested.join(",");

  const [artifacts, setArtifacts] = useState<SongArtifacts>(blankArtifacts);
  const [loading, setLoading] = useState(false);
  const [nonce, setNonce] = useState(0);
  const cancelledRef = useRef<{ done: boolean }>({ done: false });

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    const run = { done: false };
    cancelledRef.current.done = true;
    cancelledRef.current = run;

    if (!song) {
      setArtifacts(blankArtifacts());
      setLoading(false);
      return;
    }

    // seed every requested key to "loading", others stay "idle"
    setArtifacts(blankArtifacts({ keys: requested, status: "loading" }));
    setLoading(true);

    let settled = 0;
    for (const key of requested) {
      const load = artifactLoaders[key] as (
        s: string,
      ) => Promise<
        | { ok: true; data: ArtifactData<typeof key> }
        | { ok: false; error: LoadError }
      >;
      void load(song).then((result) => {
        if (run.done) return;
        setArtifacts(
          (current) =>
            ({
              ...current,
              [key]: result.ok
                ? { status: "ready", data: result.data, error: null }
                : { status: "error", data: null, error: result.error },
            }) as SongArtifacts,
        );
        settled += 1;
        if (settled === requested.length) setLoading(false);
      });
    }

    return () => {
      run.done = true;
    };
  }, [song, requestedSig, nonce]); // eslint-disable-line react-hooks/exhaustive-deps

  return { song, loading, artifacts, reload };
}
