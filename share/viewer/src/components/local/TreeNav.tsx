import { Folder } from 'lucide-react'
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
  currentPath: string,
  selected: string | null,
  onSelect: (path: string) => void,
): JSX.Element {
  const dirNames = Array.from(node.dirs.keys()).sort()

  return (
    <ul className={cn(
      "list-none space-y-0.5",
      depth > 0 && "pl-2 ml-0.5 border-l border-ink/5"
    )}>
      {dirNames.map((name) => {
        let currentName = name
        let currentNode = node.dirs.get(name)!
        
        // Squash logic: if the directory has exactly one child directory and no files, collapse it.
        while (currentNode.dirs.size === 1 && currentNode.files.length === 0) {
          const [nextName, nextNode] = Array.from(currentNode.dirs.entries())[0]
          currentName += "/" + nextName
          currentNode = nextNode
        }

        const fullPath = currentPath ? `${currentPath}/${currentName}` : currentName
        const isSelected = fullPath === selected

        return (
          <li key={`d:${currentName}`}>
            <button
              onClick={() => onSelect(fullPath)}
              className={cn(
                "flex items-center gap-1.5 w-full text-left px-2 py-1 rounded-lg text-[10px] font-black uppercase tracking-[0.10em] transition-all duration-300",
                isSelected
                  ? "bg-teal-500/10 text-teal-700 shadow-sm"
                  : "text-ink/30 hover:bg-papaya-300/30 hover:text-ink/60"
              )}
            >
              <Folder className={cn("w-2.5 h-2.5 transition-colors", isSelected ? "text-teal" : "opacity-40")} />
              <span className="truncate">{currentName}</span>
            </button>
            {renderNode(currentNode, depth + 1, fullPath, selected, onSelect)}
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
      {renderNode(tree, 0, '', selected, onSelect)}
    </div>
  )
}
