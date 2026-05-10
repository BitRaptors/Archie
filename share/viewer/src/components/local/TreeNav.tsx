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
    <ul className="list-none">
      {dirNames.map((name) => (
        <li key={`d:${name}`} style={{ paddingLeft: `${depth * 12}px` }}>
          <div className="text-papaya-300 text-xs font-semibold uppercase tracking-wide py-1">{name}/</div>
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
              className={`block w-full text-left px-2 py-1 rounded text-sm ${
                isSelected ? 'bg-teal-900 text-papaya-100' : 'text-papaya-200 hover:bg-ink-800'
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
