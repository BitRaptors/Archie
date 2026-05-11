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
    <div className="prose max-w-none lg:prose-lg prose-headings:text-ink prose-headings:font-black prose-headings:tracking-tight prose-h1:text-4xl prose-h2:text-2xl prose-p:text-ink/80 prose-p:leading-relaxed prose-li:text-ink/80 prose-strong:text-ink prose-code:bg-papaya-100 prose-code:text-teal-700 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:before:hidden prose-code:after:hidden prose-a:text-teal-700 prose-a:no-underline hover:prose-a:underline prose-blockquote:border-teal-500 prose-blockquote:text-ink/70 prose-blockquote:bg-teal-500/5 prose-blockquote:py-2 prose-blockquote:px-6 prose-blockquote:rounded-r-xl prose-blockquote:not-italic">
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
        {content}
      </ReactMarkdown>
    </div>
  )
}
