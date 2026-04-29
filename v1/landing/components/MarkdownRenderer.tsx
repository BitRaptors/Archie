"use client";

import { useMemo } from "react";

/**
 * Lightweight markdown renderer for the landing page showcase.
 * Supports: headings, blockquotes, bold, italic, inline code, code blocks,
 * lists (ordered + unordered), tables, horizontal rules, links.
 * Styled to match the landing page's dark brutalist theme.
 */
export function MarkdownRenderer({ content }: { content: string }) {
  const rendered = useMemo(() => parseMarkdown(content), [content]);
  return <div className="space-y-3">{rendered}</div>;
}

function parseMarkdown(md: string): React.ReactNode[] {
  const lines = md.split("\n");
  const nodes: React.ReactNode[] = [];
  let i = 0;
  let key = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Code block
    if (line.trimStart().startsWith("```")) {
      const lang = line.trim().slice(3);
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trimStart().startsWith("```")) {
        codeLines.push(lines[i]);
        i++;
      }
      i++; // skip closing ```
      nodes.push(
        <div key={key++} className="relative group">
          {lang && (
            <span className="absolute top-2 right-3 text-[10px] font-mono text-gray-500 uppercase tracking-wider">
              {lang}
            </span>
          )}
          <pre className="bg-black/60 border border-white/10 rounded px-4 py-3 overflow-x-auto text-[11px] md:text-xs leading-relaxed">
            <code className="text-[#39ff14]/80 font-mono">{codeLines.join("\n")}</code>
          </pre>
        </div>
      );
      continue;
    }

    // Empty line
    if (line.trim() === "") {
      i++;
      continue;
    }

    // Horizontal rule
    if (/^---+$/.test(line.trim())) {
      nodes.push(<hr key={key++} className="border-white/10 my-4" />);
      i++;
      continue;
    }

    // Table (starts with |)
    if (line.trimStart().startsWith("|")) {
      const tableLines: string[] = [];
      while (i < lines.length && lines[i].trimStart().startsWith("|")) {
        tableLines.push(lines[i]);
        i++;
      }
      // Parse: first line = header, second = separator (skip), rest = rows
      const parseRow = (row: string) =>
        row.split("|").slice(1, -1).map((c) => c.trim());

      const headers = tableLines.length > 0 ? parseRow(tableLines[0]) : [];
      const isSep = (l: string) => /^\|[\s\-:|]+\|$/.test(l.trim());
      const dataStart = tableLines.length > 1 && isSep(tableLines[1]) ? 2 : 1;
      const rows = tableLines.slice(dataStart).map(parseRow);

      nodes.push(
        <div key={key++} className="overflow-x-auto">
          <table className="w-full text-[11px] md:text-xs border-collapse">
            <thead>
              <tr className="border-b border-[#39ff14]/20">
                {headers.map((h, hi) => (
                  <th
                    key={hi}
                    className="text-left text-[#8ecae6] font-bold uppercase tracking-wider px-3 py-2"
                  >
                    {renderInline(h)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, ri) => (
                <tr key={ri} className="border-b border-white/5 hover:bg-white/[0.02]">
                  {row.map((cell, ci) => (
                    <td key={ci} className="text-gray-300 px-3 py-1.5">
                      {renderInline(cell)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      continue;
    }

    // Headings
    const headingMatch = line.match(/^(#{1,6})\s+(.+)/);
    if (headingMatch) {
      const level = headingMatch[1].length;
      const text = headingMatch[2];
      const baseClasses = "font-black uppercase tracking-wider";
      const classes: Record<number, string> = {
        1: `${baseClasses} text-base md:text-lg text-white border-b border-[#39ff14]/20 pb-2 mb-1`,
        2: `${baseClasses} text-sm md:text-base text-[#8ecae6]`,
        3: `${baseClasses} text-xs md:text-sm text-[#8ecae6]/80`,
        4: `${baseClasses} text-xs text-gray-300`,
        5: `${baseClasses} text-xs text-gray-400`,
        6: `${baseClasses} text-xs text-gray-500`,
      };
      const Tag = `h${level}` as "h1" | "h2" | "h3" | "h4" | "h5" | "h6";
      nodes.push(
        <Tag key={key++} className={classes[level]}>
          {renderInline(text)}
        </Tag>
      );
      i++;
      continue;
    }

    // Blockquote (collect consecutive > lines)
    if (line.trimStart().startsWith(">")) {
      const quoteLines: string[] = [];
      while (i < lines.length && lines[i].trimStart().startsWith(">")) {
        quoteLines.push(lines[i].replace(/^>\s?/, ""));
        i++;
      }
      nodes.push(
        <blockquote
          key={key++}
          className="border-l-2 border-[#39ff14]/40 pl-4 text-gray-400 text-[11px] md:text-xs italic leading-relaxed"
        >
          {quoteLines.map((ql, qi) => (
            <span key={qi}>
              {renderInline(ql)}
              {qi < quoteLines.length - 1 && <br />}
            </span>
          ))}
        </blockquote>
      );
      continue;
    }

    // Unordered list (collect consecutive - lines, including indented sub-items)
    if (line.trimStart().startsWith("- ")) {
      const items: string[] = [];
      while (i < lines.length && lines[i].trimStart().startsWith("- ")) {
        items.push(lines[i].replace(/^\s*-\s+/, ""));
        i++;
        // Collect indented continuation lines
        while (i < lines.length && lines[i].match(/^\s{2,}/) && !lines[i].trimStart().startsWith("- ")) {
          items[items.length - 1] += " " + lines[i].trim();
          i++;
        }
      }
      nodes.push(
        <ul key={key++} className="space-y-1 ml-2">
          {items.map((item, ii) => (
            <li
              key={ii}
              className="flex items-start gap-2 text-gray-300 text-[11px] md:text-xs leading-relaxed"
            >
              <span className="text-[#39ff14] mt-0.5 text-[8px]">&#9632;</span>
              <span>{renderInline(item)}</span>
            </li>
          ))}
        </ul>
      );
      continue;
    }

    // Ordered list (collect consecutive 1. 2. lines)
    if (/^\d+\.\s/.test(line.trimStart())) {
      const items: string[] = [];
      while (i < lines.length && /^\d+\.\s/.test(lines[i].trimStart())) {
        items.push(lines[i].replace(/^\s*\d+\.\s+/, ""));
        i++;
      }
      nodes.push(
        <ol key={key++} className="space-y-1 ml-2">
          {items.map((item, ii) => (
            <li
              key={ii}
              className="flex items-start gap-2 text-gray-300 text-[11px] md:text-xs leading-relaxed"
            >
              <span className="text-[#39ff14] font-mono text-[10px] mt-0.5 min-w-[1rem]">
                {ii + 1}.
              </span>
              <span>{renderInline(item)}</span>
            </li>
          ))}
        </ol>
      );
      continue;
    }

    // Regular paragraph
    nodes.push(
      <p key={key++} className="text-gray-300 text-[11px] md:text-xs leading-relaxed">
        {renderInline(line)}
      </p>
    );
    i++;
  }

  return nodes;
}

function renderInline(text: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  // Process: bold, italic, inline code, links
  // Order matters: bold before italic to avoid conflicts
  const regex =
    /(\*\*(.+?)\*\*)|(\*([^*]+?)\*)|(`([^`]+?)`)|(\[([^\]]+?)\]\(([^)]+?)\))/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let key = 0;

  while ((match = regex.exec(text)) !== null) {
    // Text before match
    if (match.index > lastIndex) {
      nodes.push(<span key={key++}>{text.slice(lastIndex, match.index)}</span>);
    }

    if (match[2]) {
      // Bold **text**
      nodes.push(
        <strong key={key++} className="text-white font-bold">
          {match[2]}
        </strong>
      );
    } else if (match[4]) {
      // Italic *text*
      nodes.push(
        <em key={key++} className="text-gray-400 italic">
          {match[4]}
        </em>
      );
    } else if (match[6]) {
      // Inline code `text`
      nodes.push(
        <code
          key={key++}
          className="bg-white/5 border border-white/10 text-[#39ff14]/90 px-1.5 py-0.5 rounded text-[10px] font-mono"
        >
          {match[6]}
        </code>
      );
    } else if (match[8] && match[9]) {
      // Link [text](url)
      nodes.push(
        <a
          key={key++}
          href={match[9]}
          className="text-[#8ecae6] underline decoration-[#8ecae6]/30 hover:text-[#8ecae6]/80 transition-colors"
          target="_blank"
          rel="noopener noreferrer"
        >
          {match[8]}
        </a>
      );
    }

    lastIndex = match.index + match[0].length;
  }

  // Remaining text
  if (lastIndex < text.length) {
    nodes.push(<span key={key++}>{text.slice(lastIndex)}</span>);
  }

  return nodes.length > 0 ? nodes : [text];
}
