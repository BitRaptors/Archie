'use client'
import { useState, useEffect } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { useRouter } from 'next/router'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Shield, Key, ExternalLink, AlertCircle, Loader2, CheckCircle2, Zap, GitBranch, Eye, Lock, Ghost, Layers, Rocket } from 'lucide-react'
import { cn } from '@/lib/utils'
import { theme } from '@/lib/theme'

export default function AuthPage() {
  const [token, setToken] = useState('')
  const { authenticate, isLoading, error, serverTokenMode, isAuthenticated } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!isLoading && serverTokenMode && isAuthenticated) {
      router.replace('/')
    }
  }, [isLoading, serverTokenMode, isAuthenticated, router])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await authenticate(token)
    } catch (err) {
      console.error('Authentication error:', err)
    }
  }

  if (isLoading || (serverTokenMode && isAuthenticated)) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <Loader2 className="w-8 h-8 animate-spin text-teal" />
      </div>
    )
  }

  return (
    <div className={cn("min-h-screen bg-gradient-to-br flex items-center justify-center p-4", theme.surface.pageGradient)}>
      <div className="w-full max-w-md space-y-8 animate-in fade-in zoom-in-95 duration-700">
        {/* Logo & Title */}
        <div className="text-center space-y-4">
          <div className="relative inline-block group">
            <div className="absolute -inset-1 bg-gradient-to-r from-teal to-tangerine rounded-2xl blur opacity-25 group-hover:opacity-50 transition duration-1000 group-hover:duration-200"></div>
            <div className={cn("relative flex items-center justify-center w-20 h-20 rounded-2xl bg-white border border-papaya-400 shadow-xl")}>
              <Ghost className="w-10 h-10 text-teal fill-teal/10" />
            </div>
            <div className="absolute -bottom-2 -right-2 bg-tangerine p-1.5 rounded-lg shadow-lg text-white">
              <Zap className="w-4 h-4 fill-current" />
            </div>
          </div>

          <div className="space-y-1">
            <h1 className="text-4xl font-black tracking-tight text-ink">
              Archie
            </h1>
            <p className="text-[10px] font-black uppercase tracking-[0.3em] text-ink/30">
              Warden of Architecture
            </p>
          </div>

          <p className="text-sm text-ink-300 max-w-xs mx-auto leading-relaxed">
            Architectural discovery & enforcement engine. Connect your GitHub account to begin.
          </p>
        </div>

        {/* Main Auth Card */}
        <Card className="bg-white/70 backdrop-blur-xl border-papaya-400/60 shadow-2xl rounded-[2.5rem] overflow-hidden">
          <CardContent className="p-10 space-y-8">
            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="space-y-3">
                <label htmlFor="token" className="text-[10px] font-black text-ink/40 uppercase tracking-widest flex items-center gap-2 px-1">
                  <Key className="w-3.5 h-3.5" />
                  GitHub Access Token
                </label>
                <div className="relative group">
                  <Input
                    id="token"
                    type="password"
                    value={token}
                    onChange={(e) => setToken(e.target.value)}
                    placeholder="ghp_xxxxxxxxxxxxxxxxxxxxxxxx"
                    className="h-14 px-5 font-mono text-sm bg-white/50 border-papaya-400/60 rounded-2xl focus:ring-teal/20 focus:border-teal/40 transition-all"
                    required
                  />
                  <div className="absolute right-4 top-1/2 -translate-y-1/2 h-2 w-2 rounded-full bg-papaya-400 group-focus-within:bg-teal transition-colors" />
                </div>
                <div className="flex items-center gap-2 px-1">
                  <Lock className="w-3 h-3 text-ink/20" />
                  <p className="text-[11px] font-medium text-ink/30">
                    Stored locally in your browser. Encrypted at rest.
                  </p>
                </div>
              </div>

              {error && (
                <div className={cn("flex items-start gap-3 p-4 rounded-2xl bg-brandy/5 border border-brandy/10 animate-in fade-in slide-in-from-top-1 duration-200")}>
                  <AlertCircle className="w-4 h-4 mt-0.5 shrink-0 text-brandy" />
                  <p className="text-sm text-brandy leading-tight font-medium">{error}</p>
                </div>
              )}

              <Button
                type="submit"
                disabled={isLoading || !token.trim()}
                className={cn("w-full h-14 gap-3 text-lg transition-all", theme.interactive.cta)}
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-6 h-6 animate-spin" />
                    Connecting...
                  </>
                ) : (
                  <>
                    <Rocket className="w-6 h-6" />
                    Enter Dashboard
                  </>
                )}
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* Token Help */}
        <div className="space-y-4">
          <div className="flex items-center gap-3 px-4">
            <div className="h-px flex-1 bg-papaya-300/60" />
            <span className="text-[10px] font-black uppercase tracking-widest text-ink/20">Setup Guide</span>
            <div className="h-px flex-1 bg-papaya-300/60" />
          </div>

          <Card className="bg-papaya-300/20 border-papaya-400/40 rounded-3xl">
            <CardContent className="p-8 space-y-6">
              <div className="grid gap-4">
                {[
                  { step: '01', text: 'Generate a classic PAT in GitHub settings.' },
                  { step: '02', text: 'Enable repo and read:user scopes.' },
                  { step: '03', text: 'Paste the generated token above to sync.' },
                ].map((item) => (
                  <div key={item.step} className="flex items-start gap-4">
                    <span className="flex items-center justify-center w-6 h-6 rounded-lg bg-teal/10 text-[10px] font-black text-teal tabular-nums shrink-0 mt-0.5 shadow-sm">
                      {item.step}
                    </span>
                    <p className="text-xs font-bold text-ink/60 uppercase tracking-tight leading-relaxed">{item.text}</p>
                  </div>
                ))}
              </div>

              <div className="flex items-center gap-3 pt-2">
                <Badge variant="secondary" className="bg-teal/5 text-teal border-teal/10 font-mono text-[9px] h-6 px-2">
                  repo
                </Badge>
                <Badge variant="secondary" className="bg-teal/5 text-teal border-teal/10 font-mono text-[9px] h-6 px-2">
                  read:user
                </Badge>
              </div>

              <div className="flex gap-2 pt-2">
                <Button variant="outline" size="sm" className="flex-1 h-10 gap-2 border-papaya-400 rounded-xl hover:bg-white text-xs font-bold" asChild>
                  <a
                    href="https://github.com/settings/tokens"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <GitBranch className="w-3.5 h-3.5 text-ink/40" />
                    Create Token
                    <ExternalLink className="w-3 w-3 text-ink/20" />
                  </a>
                </Button>
                <Button variant="ghost" size="sm" className="flex-1 h-10 gap-2 text-ink/40 hover:text-ink/60 hover:bg-papaya-300/20 rounded-xl text-xs font-bold" asChild>
                  <a
                    href="https://docs.github.com/en/authentication"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <Eye className="w-3.5 h-3.5" />
                    Help
                    <ExternalLink className="w-3 w-3" />
                  </a>
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="text-center">
          <p className="text-[10px] font-black uppercase tracking-[0.2em] text-ink/10">
            Encrypted & Secured Workspace
          </p>
        </div>
      </div>
    </div>
  )
}
