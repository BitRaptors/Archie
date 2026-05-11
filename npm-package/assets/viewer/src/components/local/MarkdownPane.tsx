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
// divergent markdown configs. Light-palette `prose` styling so the panes feel
// native next to the cream + ink + teal blueprint shell.
export default function MarkdownPane({ content }: Props) {
  return (
    <div className="prose prose-sm max-w-none prose-headings:text-ink prose-headings:font-black prose-p:text-ink/80 prose-li:text-ink/80 prose-strong:text-ink prose-code:bg-papaya-100 prose-code:text-teal-700 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:before:hidden prose-code:after:hidden prose-a:text-teal-700 prose-a:no-underline hover:prose-a:underline prose-blockquote:border-teal-500 prose-blockquote:text-ink/70">
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
        {content}
      </ReactMarkdown>
    </div>
  )
}
