
import { useState, useEffect } from 'react'
import { Shell } from '@/components/layout/Shell'
import { Sidebar } from '@/components/layout/Sidebar'
import { RepositoryView } from '@/components/views/RepositoryView'
import { AnalysisView } from '@/components/views/AnalysisView'
import { BlueprintView } from '@/components/views/BlueprintView'
import { SettingsView } from '@/components/views/SettingsView'
import { Loader2 } from 'lucide-react'
import { useWorkspaceRepositories, useActiveRepository } from '@/hooks/api/useWorkspace'

type ViewState = 'repositories' | 'analysis' | 'blueprint' | 'settings'

export default function Dashboard() {
  const { data: history = [] } = useWorkspaceRepositories()
  const { data: activeRepo, isLoading: isActiveLoading } = useActiveRepository()

  // SPA State
  const [activeView, setActiveView] = useState<ViewState>('repositories')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [repoId, setRepoId] = useState<string | null>(null)
  const [initialLoadDone, setInitialLoadDone] = useState(false)
  const [initialBlueprintTab, setInitialBlueprintTab] = useState<'backend' | 'delivery' | undefined>(undefined)

  // Handle initial view state based on active repository
  useEffect(() => {
    if (!isActiveLoading && activeRepo?.active_repo_id && !initialLoadDone) {
      setRepoId(activeRepo.active_repo_id)
      setActiveView('blueprint')
      setInitialLoadDone(true)
    } else if (!isActiveLoading && !initialLoadDone) {
      setInitialLoadDone(true)
    }
  }, [isActiveLoading, activeRepo, initialLoadDone])

  // Sync repoId with activeRepo if it changes elsewhere
  useEffect(() => {
    if (activeRepo?.active_repo_id && repoId !== activeRepo.active_repo_id && initialLoadDone) {
      // If we are currently in blueprint view and have a repoId, maybe we don't want to force sync
      // but if we don't have a repoId set, we should probably take the active one
      if (activeView === 'blueprint' && !repoId && !selectedId) {
        setRepoId(activeRepo.active_repo_id)
      }
    }
  }, [activeRepo, repoId, initialLoadDone, activeView, selectedId])

  // Hydration check
  const [mounted, setMounted] = useState(false)
  useEffect(() => { setMounted(true) }, [])

  if (!mounted || (!initialLoadDone && isActiveLoading)) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    )
  }

  // Navigation Handlers
  const handleNavigate = (view: ViewState) => {
    setActiveView(view)
    setSelectedId(null)
    setInitialBlueprintTab(undefined)
    // Keep repoId if it's the active one
    if (activeRepo?.active_repo_id) {
      setRepoId(activeRepo.active_repo_id)
    } else {
      setRepoId(null)
    }
  }

  const handleAnalyze = (id: string, name: string) => {
    setSelectedId(id)
    setRepoId(null)
    setInitialBlueprintTab(undefined)
    setActiveView('analysis')
  }

  const handleViewBlueprint = (id: string) => {
    setSelectedId(id)
    setRepoId(null)
    setInitialBlueprintTab(undefined)
    setActiveView('blueprint')
  }

  const handleHistoryClick = (id: string, name: string) => {
    setRepoId(id)
    setSelectedId(null)
    setInitialBlueprintTab(undefined)
    setActiveView('blueprint')
  }

  const handleActiveClick = (id: string, name: string) => {
    setRepoId(id)
    setSelectedId(null)
    setInitialBlueprintTab('delivery')
    setActiveView('blueprint')
  }

  const handleBackToDashboard = () => {
    setActiveView('repositories')
    setSelectedId(null)
    setInitialBlueprintTab(undefined)
    // Switch back to active repo if exists
    setRepoId(activeRepo?.active_repo_id || null)
  }

  const handleBackToAnalysis = () => {
    if (selectedId) {
      setActiveView('analysis')
    } else {
      setActiveView('repositories')
      setInitialBlueprintTab(undefined)
      setRepoId(activeRepo?.active_repo_id || null)
    }
  }

  return (
    <Shell
      sidebar={
        <Sidebar
          activeView={activeView}
          onNavigate={handleNavigate}
          history={history}
          onHistoryClick={handleHistoryClick}
          activeRepoId={activeRepo?.active_repo_id || undefined}
          openedRepoId={(activeView === 'blueprint' || activeView === 'analysis') ? (repoId || selectedId || undefined) : undefined}
          onActiveClick={handleActiveClick}
        />
      }
    >
      {activeView === 'repositories' && (
        <RepositoryView
          onAnalyze={handleAnalyze}
          onViewBlueprint={(repoId) => handleHistoryClick(repoId, '')}
          activeRepoId={activeRepo?.active_repo_id || undefined}
          onNavigateToSettings={() => handleNavigate('settings')}
        />
      )}

      {activeView === 'analysis' && selectedId && (
        <AnalysisView
          analysisId={selectedId}
          onViewBlueprint={handleViewBlueprint}
          onBack={handleBackToDashboard}
        />
      )}

      {activeView === 'blueprint' && (selectedId || repoId) && (
        <BlueprintView
          analysisId={selectedId || undefined}
          repoId={repoId || undefined}
          initialTab={initialBlueprintTab as any}
          onBack={handleBackToAnalysis}
          onAnalyze={handleAnalyze}
        />
      )}

      {activeView === 'settings' && <SettingsView />}
    </Shell>
  )
}
