import type { AppProps } from 'next/app'
import { QueryClient, QueryClientProvider, MutationCache, QueryCache } from '@tanstack/react-query'
import { AuthContextProvider } from '@/context/auth'
import { Toaster, toast } from 'sonner'
import '@/styles/globals.css'
import Head from 'next/head'

function extractErrorMessage(error: unknown): string {
  const err = error as any
  // Axios error with response body
  const detail = err?.response?.data?.detail
  if (detail) {
    if (typeof detail === 'string') return detail
    if (detail.message) return detail.message
    if (detail.errors) return detail.errors.join('. ')
  }
  return err?.message || 'An unexpected error occurred'
}

const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (error) => {
      toast.error(extractErrorMessage(error))
    },
  }),
  mutationCache: new MutationCache({
    onError: (error) => {
      toast.error(extractErrorMessage(error))
    },
  }),
})

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
          <Toaster position="bottom-right" richColors closeButton />
        </AuthContextProvider>
      </QueryClientProvider>
    </>
  )
}
