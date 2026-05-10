import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import 'highlight.js/styles/atom-one-dark.min.css'

interface Props {
  content: string
}

// Shared markdown surface for the local viewer's tab panes (Generated Files,
// Folder CLAUDE.mds). Mirrors the plugin set used in ReportPage's executive
// summary block (remark-gfm + rehype-highlight) so we don't drift into two
// divergent markdown configs. The `prose-invert` palette matches the dark
// surfaces used in the local-only browsers.
export default function MarkdownPane({ content }: Props) {
  return (
    <div className="prose prose-invert prose-sm max-w-none">
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
        {content}
      </ReactMarkdown>
    </div>
  )
}
