import { Html, Head, Main, NextScript } from 'next/document'

export default function Document() {
  return (
    <Html lang="en">
      <Head>
        <meta charSet="utf-8" />
        <meta name="description" content="Repository Analysis System - Analyze GitHub repositories and generate architecture blueprints" />
        <link rel="icon" type="image/svg+xml" href="/archie-logo.svg" />
      </Head>
      <body>
        <Main />
        <NextScript />
      </body>
    </Html>
  )
}


