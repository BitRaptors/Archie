import type { AppProps } from 'next/app'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthContextProvider } from '@/context/auth'
import '@/styles/globals.css'
import Head from 'next/head'

const queryClient = new QueryClient()

export default function App({ Component, pageProps }: AppProps) {
  return (
    <>
      <Head>
        <title>Repository Analysis System</title>
        <meta name="description" content="Analyze GitHub repositories and generate architecture blueprints" />
      </Head>
      <QueryClientProvider client={queryClient}>
        <AuthContextProvider>
          <Component {...pageProps} />
        </AuthContextProvider>
      </QueryClientProvider>
    </>
  )
}

