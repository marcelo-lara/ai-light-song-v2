import { useMemo, useState } from "react";

import {
  buildJsonTree,
  containerSummary,
  defaultExpandedPaths,
  formatJsonPath,
  formatLeaf,
  isContainer,
  type JsonNode,
} from "./jsonTree";

interface JsonTreeProps {
  value: unknown;
  /** Called with a node's accessor path (`$.beats[0].time`) on "copy path". */
  onCopyPath: (path: string) => void;
}

/** Read-only collapsible JSON tree. No external lib. */
export function JsonTree({ value, onCopyPath }: JsonTreeProps): React.JSX.Element {
  const root = useMemo(() => buildJsonTree(value), [value]);
  const [expanded, setExpanded] = useState<Set<string>>(() =>
    defaultExpandedPaths(root, 1),
  );

  const toggle = (pathKey: string): void => {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(pathKey)) next.delete(pathKey);
      else next.add(pathKey);
      return next;
    });
  };

  return (
    <div className="json-tree" role="tree">
      <JsonNodeRow
        node={root}
        expanded={expanded}
        onToggle={toggle}
        onCopyPath={onCopyPath}
      />
    </div>
  );
}

interface RowProps {
  node: JsonNode;
  expanded: Set<string>;
  onToggle: (pathKey: string) => void;
  onCopyPath: (path: string) => void;
}

function JsonNodeRow({
  node,
  expanded,
  onToggle,
  onCopyPath,
}: RowProps): React.JSX.Element {
  const pathKey = formatJsonPath(node.path);
  const container = isContainer(node);
  const isOpen = container && expanded.has(pathKey);
  const label =
    node.key === null ? "root" : typeof node.key === "number" ? `${node.key}` : node.key;

  return (
    <div className="json-tree__node" role="treeitem" aria-expanded={container ? isOpen : undefined}>
      <div className="json-tree__row">
        {container ? (
          <button
            type="button"
            className="json-tree__toggle"
            aria-label={isOpen ? "Collapse" : "Expand"}
            onClick={() => onToggle(pathKey)}
          >
            <i className={`ph ${isOpen ? "ph-caret-down" : "ph-caret-right"}`} />
          </button>
        ) : (
          <span className="json-tree__toggle json-tree__toggle--leaf" />
        )}

        <span className={`json-tree__key json-tree__key--${node.key === null ? "root" : typeof node.key}`}>
          {label}
        </span>

        {container ? (
          <span className="json-tree__summary">{containerSummary(node)}</span>
        ) : (
          <span className={`json-tree__value json-tree__value--${node.kind}`}>
            {formatLeaf(node)}
          </span>
        )}

        <button
          type="button"
          className="json-tree__copy"
          title={`Copy path  ${pathKey}`}
          aria-label={`Copy path ${pathKey}`}
          onClick={() => onCopyPath(pathKey)}
        >
          <i className="ph ph-copy" />
        </button>
      </div>

      {container && isOpen && (
        <div className="json-tree__children">
          {node.children && node.children.length > 0 ? (
            node.children.map((child) => (
              <JsonNodeRow
                key={formatJsonPath(child.path)}
                node={child}
                expanded={expanded}
                onToggle={onToggle}
                onCopyPath={onCopyPath}
              />
            ))
          ) : (
            <div className="json-tree__row json-tree__row--empty">
              <span className="json-tree__toggle json-tree__toggle--leaf" />
              <span className="json-tree__summary">empty</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
