export function Footer() {
  return (
    <footer className="bg-black py-16 px-4 border-t-2 border-gray-800 text-center text-gray-500 font-mono text-sm">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-center gap-6">
        <a
          href="https://bitraptors.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-base hover:text-neon transition-colors"
        >
          Made with ❤️ by BitRaptors
        </a>
        <div className="flex gap-8 text-base underline decoration-gray-800 underline-offset-4">
          <a
            href="https://github.com/BitRaptors/Archie/blob/main/docs/ARCHITECTURE.md"
            className="hover:text-neon hover:decoration-neon transition-colors"
          >
            Documentation
          </a>
          <a
            href="https://github.com/BitRaptors/Archie"
            className="hover:text-neon hover:decoration-neon transition-colors"
          >
            GitHub
          </a>
        </div>
      </div>
    </footer>
  )
}
