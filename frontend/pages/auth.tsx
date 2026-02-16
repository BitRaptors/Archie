'use client'
import { useState, useEffect } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { useRouter } from 'next/router'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Shield, Key, ExternalLink, AlertCircle, Loader2, CheckCircle2, Zap, GitBranch, Eye, Lock } from 'lucide-react'
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
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    )
  }

  return (
    <div className={cn("min-h-screen bg-gradient-to-br flex items-center justify-center p-4", theme.surface.pageGradient)}>
      <div className="w-full max-w-md space-y-8 animate-in fade-in zoom-in-95 duration-500">
        {/* Logo & Title */}
        <div className="text-center space-y-3">
          <div className={cn("inline-flex items-center justify-center w-16 h-16 rounded-2xl mb-2", theme.brand.iconBg)}>
            <Shield className="w-8 h-8 text-white" />
          </div>
          <h1 className={cn("text-2xl font-bold tracking-tight", theme.brand.title)}>
            Architecture Blueprints
          </h1>
          <p className="text-sm text-muted-foreground max-w-xs mx-auto">
            Connect your GitHub account to analyze repositories and enforce architecture.
          </p>
        </div>

        {/* Main Auth Card */}
        <Card className={cn("shadow-lg", theme.surface.authCard)}>
          <CardContent className="p-6 space-y-5">
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <label htmlFor="token" className="text-xs font-bold text-muted-foreground uppercase tracking-widest flex items-center gap-2">
                  <Key className="w-3.5 h-3.5" />
                  Personal Access Token
                </label>
                <Input
                  id="token"
                  type="password"
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  placeholder="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                  className="h-11 font-mono text-sm"
                  required
                />
                <p className="text-[11px] text-muted-foreground flex items-center gap-1.5">
                  <Lock className="w-3 h-3" />
                  Stored locally in your browser. Never sent to our servers.
                </p>
              </div>

              {error && (
                <div className={cn("flex items-start gap-2 p-3 rounded-lg animate-in fade-in slide-in-from-top-1 duration-200", theme.status.errorPanel)}>
                  <AlertCircle className={cn("w-4 h-4 mt-0.5 shrink-0", theme.status.errorIcon)} />
                  <p className={cn("text-sm", theme.status.errorText)}>{error}</p>
                </div>
              )}

              <Button
                type="submit"
                disabled={isLoading || !token.trim()}
                className={cn("w-full h-11 gap-2", theme.interactive.cta)}
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Authenticating...
                  </>
                ) : (
                  <>
                    <Zap className="w-4 h-4 fill-current" />
                    Connect to GitHub
                  </>
                )}
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* Token Help */}
        <Card className={cn(theme.surface.panel)}>
          <CardContent className="p-5 space-y-4">
            <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-widest">
              How to get a token
            </h3>

            <div className="space-y-3">
              {[
                { step: '1', text: 'Go to GitHub Settings > Developer settings > Personal access tokens' },
                { step: '2', text: 'Click "Generate new token (classic)"' },
                { step: '3', text: 'Select the required scopes below and generate' },
              ].map((item) => (
                <div key={item.step} className="flex items-start gap-3">
                  <span className={cn("flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold shrink-0 mt-0.5", theme.brand.stepCircle)}>
                    {item.step}
                  </span>
                  <p className="text-sm text-foreground/80">{item.text}</p>
                </div>
              ))}
            </div>

            <div className="flex items-center gap-2 pt-1">
              <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Required scopes</span>
              <Badge variant="secondary" className={cn("text-[10px] font-mono", theme.brand.scopeBadge)}>
                repo
              </Badge>
              <Badge variant="secondary" className={cn("text-[10px] font-mono", theme.brand.scopeBadge)}>
                read:user
              </Badge>
            </div>

            <div className="flex gap-2 pt-1">
              <Button variant="outline" size="sm" className="text-xs gap-1.5 h-8" asChild>
                <a
                  href="https://github.com/settings/tokens"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <GitBranch className="w-3 h-3" />
                  Create Token
                  <ExternalLink className="w-3 h-3 text-muted-foreground" />
                </a>
              </Button>
              <Button variant="ghost" size="sm" className="text-xs gap-1.5 h-8 text-muted-foreground" asChild>
                <a
                  href="https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <Eye className="w-3 h-3" />
                  Docs
                  <ExternalLink className="w-3 h-3" />
                </a>
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
