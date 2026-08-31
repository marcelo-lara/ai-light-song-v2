import { useCallback, useEffect, useMemo, useState } from "react";

import { encodePath } from "../data/paths";
import { JsonTree } from "./JsonTree";
import { fileKind, groupByDir, walkDataDir, type WalkedFile } from "./walk";

interface ArtifactInspectorProps {
  song: string | null;
}

type ListState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; files: WalkedFile[] }
  | { status: "error"; message: string };

type FileState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "json"; data: unknown; raw: string }
  | { status: "text"; raw: string }
  | { status: "binary" }
  | { status: "error"; message: string };

/**
 * Read-only raw-artifact browser (plan item 8 / Story 8.9). Recursively walks the
 * song's analysis directory over the dev-server `/data` listing endpoint and
 * renders any selected JSON as a collapsible tree with a copy-path action.
 *
 * The walk starts at `data/analysis/<song>` (not just `artifacts/`) so every file
 * the previous app's inspector exposed — including the top-level `info.json` / `beats.json`
 * / `sections.json` / `song_event_timeline.json` / `beatdrop_visual_plan.json`
 * and `reference/human/*` — stays reachable. See D5 in the implementation plan.
 *
 * No write path: this component only ever issues GETs.
 */
export function ArtifactInspector({ song }: ArtifactInspectorProps): React.JSX.Element {
  const [list, setList] = useState<ListState>({ status: "idle" });
  const [selected, setSelected] = useState<string | null>(null);
  const [file, setFile] = useState<FileState>({ status: "idle" });
  const [copied, setCopied] = useState<string | null>(null);

  useEffect(() => {
    setSelected(null);
    setFile({ status: "idle" });
    if (!song) {
      setList({ status: "idle" });
      return;
    }
    let cancelled = false;
    setList({ status: "loading" });
    walkDataDir(["data", "analysis", song])
      .then((files) => {
        if (!cancelled) setList({ status: "ready", files });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setList({
          status: "error",
          message: error instanceof Error ? error.message : "Directory walk failed.",
        });
      });
    return () => {
      cancelled = true;
    };
  }, [song]);

  useEffect(() => {
    if (!selected) {
      setFile({ status: "idle" });
      return;
    }
    const kind = fileKind(selected.split("/").at(-1) ?? selected);
    if (kind === "binary") {
      setFile({ status: "binary" });
      return;
    }
    let cancelled = false;
    setFile({ status: "loading" });
    fetch(selected, { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`Fetch failed (${response.status}).`);
        }
        const raw = await response.text();
        if (cancelled) return;
        if (kind === "json") {
          try {
            setFile({ status: "json", data: JSON.parse(raw) as unknown, raw });
          } catch (parseError) {
            setFile({
              status: "error",
              message:
                parseError instanceof Error
                  ? `Invalid JSON: ${parseError.message}`
                  : "Invalid JSON.",
            });
          }
        } else {
          setFile({ status: "text", raw });
        }
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setFile({
          status: "error",
          message: error instanceof Error ? error.message : "Fetch failed.",
        });
      });
    return () => {
      cancelled = true;
    };
  }, [selected]);

  const groups = useMemo(
    () => (list.status === "ready" ? groupByDir(list.files) : []),
    [list],
  );

  const selectedFile = useMemo(
    () =>
      list.status === "ready"
        ? list.files.find((candidate) => candidate.url === selected) ?? null
        : null,
    [list, selected],
  );

  const handleCopyPath = useCallback(
    (path: string) => {
      const label = selectedFile ? `${selectedFile.relativePath}  ${path}` : path;
      void navigator.clipboard?.writeText(label).catch(() => undefined);
      setCopied(path);
      window.setTimeout(() => {
        setCopied((current) => (current === path ? null : current));
      }, 1400);
    },
    [selectedFile],
  );

  if (!song) {
    return (
      <div className="app-rightpanel" style={{ width: "100%", borderLeft: "none" }}>
        <div className="card-kicker">Artifact inspector</div>
        <p className="card-body">Select a song to browse its raw analysis artifacts.</p>
      </div>
    );
  }

  return (
    <div className="inspector">
      <aside className="inspector__list card">
        <div className="card-kicker">Artifacts — {song}</div>
        {list.status === "loading" && <p className="card-body">Walking the artifact tree…</p>}
        {list.status === "error" && (
          <p className="card-body inspector__error">Listing failed: {list.message}</p>
        )}
        {list.status === "ready" && list.files.length === 0 && (
          <p className="card-body">No files under data/analysis/{song}.</p>
        )}
        {list.status === "ready" && list.files.length > 0 && (
          <table className="table inspector__files">
            <tbody>
              {groups.map((group) => (
                <FileGroupRows
                  key={group.dir || "<root>"}
                  dir={group.dir}
                  files={group.files}
                  selected={selected}
                  onSelect={setSelected}
                />
              ))}
            </tbody>
          </table>
        )}
      </aside>

      <section className="inspector__view card">
        {file.status === "idle" && (
          <p className="card-body">Select a file to view its contents.</p>
        )}
        {file.status === "loading" && <p className="card-body">Loading {selectedFile?.name}…</p>}
        {file.status === "binary" && (
          <p className="card-body">
            {selectedFile?.name} is a binary artifact ({selectedFile?.relativePath}) — not
            rendered here.
          </p>
        )}
        {file.status === "error" && (
          <p className="card-body inspector__error">{file.message}</p>
        )}
        {file.status === "text" && (
          <>
            <ViewHeader file={selectedFile} copied={copied} />
            <pre className="inspector__raw">{file.raw}</pre>
          </>
        )}
        {file.status === "json" && (
          <>
            <ViewHeader file={selectedFile} copied={copied} />
            <JsonTree value={file.data} onCopyPath={handleCopyPath} />
          </>
        )}
      </section>
    </div>
  );
}

function ViewHeader({
  file,
  copied,
}: {
  file: WalkedFile | null;
  copied: string | null;
}): React.JSX.Element {
  return (
    <div className="inspector__view-header">
      <span className="inspector__view-path">{file?.relativePath ?? ""}</span>
      {copied && <span className="inspector__copied">copied {copied}</span>}
    </div>
  );
}

function FileGroupRows({
  dir,
  files,
  selected,
  onSelect,
}: {
  dir: string;
  files: WalkedFile[];
  selected: string | null;
  onSelect: (url: string) => void;
}): React.JSX.Element {
  return (
    <>
      <tr className="inspector__dir">
        <th scope="rowgroup">{dir === "" ? "/" : `${dir}/`}</th>
      </tr>
      {files.map((file) => (
        <tr
          key={file.url}
          className={`inspector__file${file.url === selected ? " is-selected" : ""}`}
        >
          <td>
            <button
              type="button"
              className="inspector__file-btn"
              aria-current={file.url === selected ? "true" : undefined}
              onClick={() => onSelect(file.url)}
            >
              {file.name}
            </button>
          </td>
        </tr>
      ))}
    </>
  );
}

/** Exposed for the reachability test: the absolute URL the inspector walk targets. */
export function inspectorWalkRoot(song: string): string {
  return encodePath(["data", "analysis", song]) + "/";
}
