import { Folder, FileText } from 'lucide-react'
import { cn } from '@/lib/utils'

interface Props {
  paths: string[]
  selected: string | null
  onSelect: (path: string) => void
}

interface TreeNode {
  files: string[] // full paths whose parent is this directory
  dirs: Map<string, TreeNode>
}

function emptyNode(): TreeNode {
  return { files: [], dirs: new Map() }
}

function buildTree(paths: string[]): TreeNode {
  const root = emptyNode()
  for (const p of paths) {
    const parts = p.split('/')
    let cur = root
    for (let i = 0; i < parts.length - 1; i += 1) {
      const dir = parts[i]
      let next = cur.dirs.get(dir)
      if (!next) {
        next = emptyNode()
        cur.dirs.set(dir, next)
      }
      cur = next
    }
    cur.files.push(p)
  }
  return root
}

function renderNode(
  node: TreeNode,
  depth: number,
  selected: string | null,
  onSelect: (path: string) => void,
): JSX.Element {
  const dirNames = Array.from(node.dirs.keys()).sort()
  const files = [...node.files].sort()

  return (
    <ul className={cn(
      "list-none space-y-1",
      depth > 0 && "pl-4 ml-1 border-l border-ink/5 pt-1"
    )}>
      {dirNames.map((name) => (
        <li key={`d:${name}`}>
          <div className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.12em] text-ink/30 py-1.5 px-2">
            <Folder className="w-3 h-3 opacity-50" />
            <span>{name}</span>
          </div>
          {renderNode(node.dirs.get(name)!, depth + 1, selected, onSelect)}
        </li>
      ))}
      {files.map((path) => {
        const label = path.split('/').pop() || path
        const isSelected = path === selected
        return (
          <li key={`f:${path}`}>
            <button
              onClick={() => onSelect(path)}
              className={cn(
                "flex items-center gap-2.5 w-full text-left px-3 py-2 rounded-xl text-sm transition-all duration-300",
                isSelected
                  ? "bg-teal-500/10 text-teal-700 font-bold shadow-sm"
                  : "text-ink/60 hover:bg-papaya-300/30 hover:text-ink font-medium"
              )}
            >
              <FileText className={cn("w-3.5 h-3.5", isSelected ? "text-teal" : "text-ink/20")} />
              <span className="truncate">{label}</span>
            </button>
          </li>
        )
      })}
    </ul>
  )
}

export default function TreeNav({ paths, selected, onSelect }: Props) {
  const tree = buildTree(paths)
  return (
    <div className="animate-in fade-in slide-in-from-left-4 duration-500">
      {renderNode(tree, 0, selected, onSelect)}
    </div>
  )
}
