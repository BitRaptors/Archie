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
    <ul className="list-none space-y-0.5">
      {dirNames.map((name) => (
        <li key={`d:${name}`} style={{ paddingLeft: `${depth * 12}px` }}>
          <div className="text-[10px] font-black uppercase tracking-[0.18em] text-ink/40 py-1.5 px-2">
            {name}/
          </div>
          {renderNode(node.dirs.get(name)!, depth + 1, selected, onSelect)}
        </li>
      ))}
      {files.map((path) => {
        const label = path.split('/').pop() || path
        const isSelected = path === selected
        return (
          <li key={`f:${path}`} style={{ paddingLeft: `${depth * 12}px` }}>
            <button
              onClick={() => onSelect(path)}
              className={`block w-full text-left px-3 py-2 rounded-xl text-sm transition-all duration-300 ${
                isSelected
                  ? 'bg-teal-500/10 text-teal-700 font-bold shadow-sm'
                  : 'text-ink/60 hover:bg-papaya-300/30 hover:text-ink font-medium'
              }`}
            >
              {label}
            </button>
          </li>
        )
      })}
    </ul>
  )
}

export default function TreeNav({ paths, selected, onSelect }: Props) {
  const tree = buildTree(paths)
  return renderNode(tree, 0, selected, onSelect)
}
