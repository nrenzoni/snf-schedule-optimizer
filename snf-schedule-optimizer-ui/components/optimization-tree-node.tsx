"use client";

import React, { useState } from "react";
import { ChevronRight, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import type { TreeNode } from "@/lib/optimization-tree-data";

interface OptimizationTreeNodeProps {
  node: TreeNode;
  depth: number;
}

export default function OptimizationTreeNode({
  node,
  depth,
}: OptimizationTreeNodeProps) {
  const [expanded, setExpanded] = useState(node.defaultExpanded ?? false);
  const hasChildren = node.children && node.children.length > 0;

  return (
    <div>
      <div
        data-testid={`tree-node-${node.id}`}
        role="treeitem"
        aria-expanded={hasChildren ? expanded : undefined}
        aria-selected="false"
        tabIndex={0}
        className={cn(
          "flex w-full items-center gap-1.5 rounded px-2 py-1.5 text-sm transition-colors",
          hasChildren
            ? "cursor-pointer hover:bg-muted/60"
            : "cursor-default",
        )}
        style={{ paddingLeft: `${depth * 20 + 8}px` }}
        onClick={() => {
          if (hasChildren) setExpanded(!expanded);
        }}
        onKeyDown={(e) => {
          if (hasChildren && (e.key === "Enter" || e.key === " ")) {
            e.preventDefault();
            setExpanded(!expanded);
          }
        }}
      >
        {hasChildren ? (
          expanded ? (
            <ChevronDown size={14} className="shrink-0 text-muted-foreground" />
          ) : (
            <ChevronRight size={14} className="shrink-0 text-muted-foreground" />
          )
        ) : (
          <span className="w-3.5 shrink-0" />
        )}
        <span className="truncate font-medium text-foreground">{node.label}</span>
        {node.value !== undefined && (
          <span className="ml-auto shrink-0 whitespace-nowrap pl-2 font-mono text-xs tabular-nums text-muted-foreground">
            {node.value}
          </span>
        )}
      </div>
      {expanded && hasChildren
        ? node.children!.map((child) => (
            <OptimizationTreeNode
              key={child.id}
              node={child}
              depth={depth + 1}
            />
          ))
        : null}
    </div>
  );
}
