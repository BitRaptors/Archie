"use client";

import { useState, useMemo } from "react";
import { ChevronRight, FileText, Folder, FolderOpen } from "lucide-react";

interface TreeNode {
  name: string;
  path: string; // full relative path for files, dir path for folders
  isDir: boolean;
  children: TreeNode[];
}

function buildTree(paths: string[]): TreeNode[] {
  const root: TreeNode = { name: "", path: "", isDir: true, children: [] };

  for (const filePath of paths) {
    const parts = filePath.split("/");
    let current = root;
    let accumulated = "";

    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      accumulated = accumulated ? `${accumulated}/${part}` : part;
      const isLast = i === parts.length - 1;

      if (isLast) {
        current.children.push({
          name: part,
          path: filePath,
          isDir: false,
          children: [],
        });
      } else {
        let dir = current.children.find((c) => c.isDir && c.name === part);
        if (!dir) {
          dir = { name: part, path: accumulated, isDir: true, children: [] };
          current.children.push(dir);
        }
        current = dir;
      }
    }
  }

  // Sort: directories first, then files, both alphabetical
  function sortTree(nodes: TreeNode[]): TreeNode[] {
    return nodes
      .map((n) => (n.isDir ? { ...n, children: sortTree(n.children) } : n))
      .sort((a, b) => {
        if (a.isDir !== b.isDir) return a.isDir ? -1 : 1;
        return a.name.localeCompare(b.name);
      });
  }

  return sortTree(root.children);
}

// Icon color for known file types
function getFileColor(name: string): string {
  if (name === "CLAUDE.md") return "text-[#39ff14]";
  if (name === "CODEBASE_MAP.md") return "text-[#ffb703]";
  if (name === "AGENTS.md") return "text-[#8ecae6]";
  if (name.endsWith(".md")) return "text-gray-400";
  if (name.endsWith(".json")) return "text-[#fb8500]";
  if (name.endsWith(".sh")) return "text-[#219ebc]";
  return "text-gray-500";
}

function TreeItem({
  node,
  depth,
  activePath,
  onSelect,
  defaultExpanded,
}: {
  node: TreeNode;
  depth: number;
  activePath: string;
  onSelect: (path: string) => void;
  defaultExpanded: boolean;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const isActive = !node.isDir && node.path === activePath;
  const containsActive = node.isDir && activePath.startsWith(node.path + "/");

  // Auto-expand when navigating into this folder
  const shouldExpand = expanded || containsActive;

  if (node.isDir) {
    return (
      <div>
        <button
          onClick={() => setExpanded(!shouldExpand)}
          className={`w-full flex items-center gap-1.5 py-1 px-2 text-left text-[11px] hover:bg-white/5 transition-colors rounded-sm group ${
            containsActive ? "text-white" : "text-gray-500 hover:text-gray-300"
          }`}
          style={{ paddingLeft: `${depth * 12 + 8}px` }}
        >
          <ChevronRight
            className={`w-3 h-3 shrink-0 transition-transform duration-150 ${
              shouldExpand ? "rotate-90" : ""
            }`}
          />
          {shouldExpand ? (
            <FolderOpen className="w-3.5 h-3.5 shrink-0 text-[#ffb703]/70" />
          ) : (
            <Folder className="w-3.5 h-3.5 shrink-0 text-[#ffb703]/50" />
          )}
          <span className="font-mono truncate">{node.name}/</span>
          <span className="ml-auto text-[9px] text-gray-700 font-mono opacity-0 group-hover:opacity-100 transition-opacity">
            {node.children.length}
          </span>
        </button>
        {shouldExpand && (
          <div>
            {node.children.map((child) => (
              <TreeItem
                key={child.path}
                node={child}
                depth={depth + 1}
                activePath={activePath}
                onSelect={onSelect}
                defaultExpanded={false}
              />
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <button
      onClick={() => onSelect(node.path)}
      className={`w-full flex items-center gap-1.5 py-1 px-2 text-left text-[11px] transition-all rounded-sm ${
        isActive
          ? "bg-[#39ff14]/10 text-[#39ff14] border-l-2 border-[#39ff14]"
          : "text-gray-500 hover:text-gray-300 hover:bg-white/5 border-l-2 border-transparent"
      }`}
      style={{ paddingLeft: `${depth * 12 + 8}px` }}
    >
      <FileText className={`w-3.5 h-3.5 shrink-0 ${isActive ? "text-[#39ff14]" : getFileColor(node.name)}`} />
      <span className="font-mono truncate">{node.name}</span>
    </button>
  );
}

export function FileTree({
  filePaths,
  activePath,
  onSelect,
}: {
  filePaths: string[];
  activePath: string;
  onSelect: (path: string) => void;
}) {
  const tree = useMemo(() => buildTree(filePaths), [filePaths]);

  return (
    <div className="py-2 select-none">
      {tree.map((node) => (
        <TreeItem
          key={node.path}
          node={node}
          depth={0}
          activePath={activePath}
          onSelect={onSelect}
          defaultExpanded={
            // Expand root-level folders by default
            node.isDir && (node.name === "backend" || node.name === ".claude")
          }
        />
      ))}
    </div>
  );
}
