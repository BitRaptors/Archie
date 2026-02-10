import type { AppProps } from 'next/app'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthContextProvider } from '@/context/auth'
import '@/styles/globals.css'
import Head from 'next/head'
import Link from 'next/link'
import { useRouter } from 'next/router'

const queryClient = new QueryClient()

function NavBar() {
  const router = useRouter()

  const links = [
    { href: '/', label: 'Repositories' },
    { href: '/workspace', label: 'Workspace' },
  ]

  return (
    <nav className="border-b bg-white sticky top-0 z-30">
      <div className="container mx-auto max-w-5xl flex items-center h-12 px-4 gap-6">
        <Link href="/" className="font-bold text-gray-900 whitespace-nowrap">
          Arch MCP
        </Link>
        <div className="flex items-center gap-1">
          {links.map(({ href, label }) => {
            const isActive = router.pathname === href
            return (
              <Link
                key={href}
                href={href}
                className={`px-3 py-1.5 text-sm rounded transition-colors ${
                  isActive
                    ? 'bg-gray-100 text-gray-900 font-medium'
                    : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
                }`}
              >
                {label}
              </Link>
            )
          })}
        </div>
      </div>
    </nav>
  )
}

export default function App({ Component, pageProps }: AppProps) {
  return (
    <>
      <Head>
        <title>Repository Analysis System</title>
        <meta name="description" content="Analyze GitHub repositories and generate architecture blueprints" />
      </Head>
      <QueryClientProvider client={queryClient}>
        <AuthContextProvider>
          <NavBar />
          <Component {...pageProps} />
        </AuthContextProvider>
      </QueryClientProvider>
    </>
  )
}
