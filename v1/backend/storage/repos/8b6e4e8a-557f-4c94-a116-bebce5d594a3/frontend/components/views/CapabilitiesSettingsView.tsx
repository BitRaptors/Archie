import { useState, useEffect } from 'react'
import {
  useLibraryCapabilities,
  useUpdateLibraryCapabilities,
  useResetLibraryCapabilities,
  useCapabilityOptions,
  useEcosystemOptions,
} from '@/hooks/api/useSettings'
import { LibraryCapabilityInput } from '@/services/settings'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Save, RotateCcw, Plus, X, Trash2, Zap, Loader2, Globe, Box } from 'lucide-react'
import { cn } from '@/lib/utils'
import { theme } from '@/lib/theme'

export function CapabilitiesSettingsView() {
  const { data: rows, isLoading } = useLibraryCapabilities()
  const { data: capabilityOptions = [] } = useCapabilityOptions()
  const { data: ecosystemOptions = [] } = useEcosystemOptions()
  const updateMutation = useUpdateLibraryCapabilities()
  const resetMutation = useResetLibraryCapabilities()

  const [libs, setLibs] = useState<LibraryCapabilityInput[]>([])
  const [initialized, setInitialized] = useState(false)

  // New library form
  const [newLib, setNewLib] = useState('')
  const [newEcosystem, setNewEcosystem] = useState('')
  const [newCaps, setNewCaps] = useState<string[]>([])

  // Derive server state for dirty comparison
  const serverLibs: LibraryCapabilityInput[] = (rows ?? []).map((r) => ({
    library_name: r.library_name,
    ecosystem: r.ecosystem,
    capabilities: r.capabilities,
  }))

  useEffect(() => {
    if (rows && !initialized) {
      setLibs(
        rows.map((r) => ({
          library_name: r.library_name,
          ecosystem: r.ecosystem,
          capabilities: [...r.capabilities],
        }))
      )
      setInitialized(true)
    }
  }, [rows, initialized])

  // Sync from server after save/reset
  useEffect(() => {
    if (rows && initialized && !updateMutation.isPending && !resetMutation.isPending) {
      setLibs(
        rows.map((r) => ({
          library_name: r.library_name,
          ecosystem: r.ecosystem,
          capabilities: [...r.capabilities],
        }))
      )
    }
  }, [rows])

  const isDirty = JSON.stringify(
    [...libs].sort((a, b) => a.library_name.localeCompare(b.library_name))
  ) !== JSON.stringify(
    [...serverLibs].sort((a, b) => a.library_name.localeCompare(b.library_name))
  )

  const handleAddLibrary = () => {
    const trimmedLib = newLib.trim().toLowerCase()
    if (trimmedLib && !libs.some((l) => l.library_name === trimmedLib)) {
      setLibs([...libs, { library_name: trimmedLib, ecosystem: newEcosystem, capabilities: [...newCaps] }])
      setNewLib('')
      setNewEcosystem('')
      setNewCaps([])
    }
  }

  const handleRemoveLibrary = (name: string) => {
    setLibs(libs.filter((l) => l.library_name !== name))
  }

  const handleEcosystemChange = (name: string, ecosystem: string) => {
    setLibs(libs.map((l) => (l.library_name === name ? { ...l, ecosystem } : l)))
  }

  const handleAddCapability = (name: string, cap: string) => {
    if (cap) {
      setLibs(
        libs.map((l) =>
          l.library_name === name && !l.capabilities.includes(cap)
            ? { ...l, capabilities: [...l.capabilities, cap] }
            : l
        )
      )
    }
  }

  const handleRemoveCapability = (name: string, cap: string) => {
    setLibs(
      libs.map((l) =>
        l.library_name === name
          ? { ...l, capabilities: l.capabilities.filter((c) => c !== cap) }
          : l
      )
    )
  }

  const handleSave = () => {
    updateMutation.mutate(libs)
  }

  const handleReset = () => {
    if (window.confirm("Reset library capabilities to system defaults? Any custom mappings will be lost.")) {
      resetMutation.mutate(undefined, {
        onSuccess: () => setInitialized(false),
      })
    }
  }

  if (isLoading) {
    return (
      <Card className="border shadow-sm">
        <CardContent className="py-12 flex flex-col items-center">
          <Skeleton className="h-12 w-12 rounded-full mb-4" />
          <Skeleton className="h-4 w-64 mb-2" />
          <Skeleton className="h-4 w-48" />
        </CardContent>
      </Card>
    )
  }

  const sortedLibs = [...libs].sort((a, b) => a.library_name.localeCompare(b.library_name))

  return (
    <div className="space-y-6 animate-in slide-in-from-bottom-4 duration-500">
      <Card className={cn("border-none shadow-none bg-transparent")}>
        <div className="pb-6 border-b border-papaya-400/50">
          <h3 className="text-2xl font-bold tracking-tight text-ink">Library Capabilities Mapper</h3>
          <p className="text-sm text-ink-400 mt-1 leading-relaxed">
            Connect libraries to specific functionalities to help the AI understand your stack.
          </p>
        </div>

        <div className="mt-8 space-y-8">
          <div className={cn("p-5 rounded-2xl border flex gap-4 bg-white/40 border-papaya-400/50")}>
            <div className="w-10 h-10 rounded-full bg-white border border-papaya-400/50 flex items-center justify-center shrink-0">
              <Zap className="w-5 h-5 text-ink/40" />
            </div>
            <div className="text-[13px] text-ink-400 leading-relaxed">
              <p className="font-bold uppercase tracking-wider mb-0.5 text-ink">Optimization Engine</p>
              The AI uses this registry to avoid recommending duplicate libraries for capabilities already present in your project.
            </div>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <label className="text-[11px] font-black text-ink/40 uppercase tracking-widest block">
                Capability Registry
              </label>
              <div className="text-[10px] font-bold text-ink/20 uppercase tracking-tighter">
                {libs.length} LIBRARIES REGISTERED
              </div>
            </div>

            <div className="border border-papaya-400/50 rounded-2xl shadow-sm overflow-hidden bg-white/40">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-papaya-300/20 border-b border-papaya-400/50">
                    <th className="px-6 py-4 text-[11px] font-black uppercase tracking-widest text-ink/40">Library & Ecosystem</th>
                    <th className="px-6 py-4 text-[11px] font-black uppercase tracking-widest text-ink/40">Capabilities Mapping</th>
                    <th className="px-6 py-4 w-16" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-papaya-400/30">
                  {sortedLibs.map((lib) => (
                    <tr key={lib.library_name} className="group hover:bg-papaya-50/50 transition-colors">
                      <td className="px-6 py-6 align-top">
                        <div className="flex flex-col gap-3">
                          <div className="flex items-center gap-2">
                            <Box className="w-4 h-4 text-teal" />
                            <span className="font-mono text-sm font-bold text-ink">{lib.library_name}</span>
                          </div>
                          <div className="relative">
                            <Globe className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-ink-300 pointer-events-none" />
                            <select
                              value={lib.ecosystem}
                              onChange={(e) => handleEcosystemChange(lib.library_name, e.target.value)}
                              className="w-full h-9 pl-8 pr-8 text-xs font-bold uppercase tracking-wider border border-papaya-200 rounded-lg bg-papaya-50/30 focus:bg-white focus:border-teal/30 focus:ring-1 focus:ring-teal/20 transition-all outline-none cursor-pointer appearance-none text-ink shadow-sm"
                            >
                              <option value="" disabled>Select ecosystem...</option>
                              {ecosystemOptions.map((opt) => (
                                <option key={opt} value={opt}>{opt}</option>
                              ))}
                            </select>
                            <div className="absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none text-ink/20">
                              <Plus className="w-3 h-3 rotate-45" />
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-6 align-top">
                        <div className="flex flex-wrap gap-2 mb-4">
                          {lib.capabilities.map((cap) => (
                            <Badge
                              key={cap}
                              variant="secondary"
                              className="gap-2 pl-3 pr-1.5 py-1.5 text-[10px] font-bold uppercase tracking-wide bg-white border border-teal-100 text-teal-700 hover:bg-teal-50 transition-all shadow-sm rounded-md"
                            >
                              {cap.replace(/_/g, ' ')}
                              <button
                                className="p-0.5 rounded-md hover:bg-teal-100 transition-colors"
                                onClick={() => handleRemoveCapability(lib.library_name, cap)}
                              >
                                <X className="w-3 h-3" />
                              </button>
                            </Badge>
                          ))}
                          {lib.capabilities.length === 0 && (
                            <span className="text-[10px] text-ink/20 italic py-1.5">No capabilities defined</span>
                          )}
                        </div>
                        <div className="relative max-w-sm">
                          <select
                            className="h-9 w-full text-[10px] font-black uppercase tracking-widest bg-white border border-papaya-200 rounded-lg px-4 pr-8 focus:border-teal/30 focus:ring-1 focus:ring-teal/20 transition-all outline-none cursor-pointer text-ink appearance-none shadow-sm"
                            value=""
                            onChange={(e) => {
                              if (e.target.value) {
                                handleAddCapability(lib.library_name, e.target.value)
                              }
                            }}
                          >
                            <option value="" disabled>+ Add capability...</option>
                            {capabilityOptions
                              .filter((opt) => !lib.capabilities.includes(opt))
                              .map((opt) => (
                                <option key={opt} value={opt}>
                                  {opt.replace(/_/g, ' ')}
                                </option>
                              ))
                            }
                          </select>
                          <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-ink/20">
                            <Plus className="w-3 h-3" />
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-6 text-right align-top">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="w-9 h-9 text-ink-300 hover:text-brandy hover:bg-brandy/10 transition-all opacity-0 group-hover:opacity-100"
                          onClick={() => handleRemoveLibrary(lib.library_name)}
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                  {sortedLibs.length === 0 && (
                    <tr>
                      <td colSpan={3} className="px-6 py-16 text-center">
                        <div className="flex flex-col items-center">
                          <Box className="w-12 h-12 text-papaya-400/50 mb-4" />
                          <p className="text-base font-bold text-ink/20">No libraries mapped yet</p>
                        </div>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div className="p-10 rounded-[32px] bg-papaya-300/20 border-2 border-dashed border-papaya-400/40 space-y-8">
            <h4 className="text-[10px] font-black text-ink/40 uppercase tracking-[0.2em] flex items-center gap-2.5">
              <Plus className="w-4 h-4 text-teal" /> Register New Library
            </h4>

            <div className="grid grid-cols-2 gap-8">
              <div className="space-y-3">
                <label className="text-[11px] font-black text-ink/30 uppercase tracking-widest ml-1 block">Library Name</label>
                <div className="relative group">
                  <Box className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-ink-300 transition-colors group-focus-within:text-teal" />
                  <Input
                    placeholder="e.g. firebase"
                    value={newLib}
                    onChange={(e) => setNewLib(e.target.value)}
                    className="h-12 pl-12 font-mono bg-white border-papaya-300 focus:ring-teal/20 rounded-xl"
                  />
                </div>
              </div>

              <div className="space-y-3">
                <label className="text-[11px] font-black text-ink/30 uppercase tracking-widest ml-1 block">Ecosystem Focus</label>
                <div className="relative group">
                  <Globe className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-ink-300 transition-colors group-focus-within:text-teal pointer-events-none" />
                  <select
                    value={newEcosystem}
                    onChange={(e) => setNewEcosystem(e.target.value)}
                    className="h-12 w-full pl-12 pr-4 bg-white border border-papaya-300 rounded-xl text-sm font-semibold text-ink focus:ring-2 focus:ring-teal/20 focus:border-teal/30 transition-all outline-none cursor-pointer appearance-none shadow-sm"
                  >
                    <option value="" disabled>Select ecosystem...</option>
                    {ecosystemOptions.map((opt) => (
                      <option key={opt} value={opt}>{opt}</option>
                    ))}
                  </select>
                  <div className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-ink/20">
                    <Plus className="w-4 h-4 rotate-45" />
                  </div>
                </div>
              </div>
            </div>

            <div className="space-y-4">
              <label className="text-[11px] font-black text-ink/30 uppercase tracking-widest ml-1 block">Capabilities</label>

              <div className="flex flex-wrap gap-2.5 min-h-[48px] p-2 bg-white/40 border border-papaya-300 rounded-2xl items-center">
                {newCaps.length === 0 && (
                  <span className="text-[11px] text-ink/20 font-medium ml-3 italic">No capabilities added yet...</span>
                )}
                {newCaps.map((cap) => (
                  <Badge
                    key={cap}
                    variant="secondary"
                    className="gap-2 pl-4 pr-2 py-2 text-[10px] font-bold uppercase tracking-wide bg-white border border-teal-100 text-teal-700 hover:bg-teal-50 transition-all shadow-sm rounded-lg"
                  >
                    {cap.replace(/_/g, ' ')}
                    <button
                      className="p-1 rounded hover:bg-teal-100 transition-colors"
                      onClick={() => setNewCaps(newCaps.filter((c) => c !== cap))}
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </Badge>
                ))}
              </div>

              <div className="flex items-center gap-4">
                <div className="relative w-full max-w-sm">
                  <select
                    className="h-11 w-full text-xs font-bold uppercase tracking-wider bg-white border border-papaya-300 rounded-xl px-4 pr-10 focus:border-teal/30 focus:ring-2 focus:ring-teal/20 transition-all outline-none cursor-pointer text-ink appearance-none shadow-sm"
                    value=""
                    onChange={(e) => {
                      if (e.target.value) {
                        setNewCaps([...newCaps, e.target.value])
                      }
                    }}
                  >
                    <option value="" disabled>+ Add capability...</option>
                    {capabilityOptions
                      .filter((opt) => !newCaps.includes(opt))
                      .map((opt) => (
                        <option key={opt} value={opt}>{opt.replace(/_/g, ' ')}</option>
                      ))
                    }
                  </select>
                  <div className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-ink/20">
                    <Plus className="w-3.5 h-3.5" />
                  </div>
                </div>
                <div className="text-[10px] text-ink/30 font-bold uppercase tracking-tighter">
                  Select key functionalities provided by this library
                </div>
              </div>
            </div>

            <div className="flex justify-end pt-4">
              <Button
                onClick={handleAddLibrary}
                disabled={!newLib.trim()}
                className={cn("h-14 px-12 gap-3 text-sm font-bold shadow-xl transition-all", theme.active.checkBtn)}
              >
                <Plus className="w-5 h-5" />
                Add Library to Registry
              </Button>
            </div>
          </div>

          <div className="flex items-center justify-end pt-8 border-t border-papaya-400/50 gap-4">
            <Button
              variant="outline"
              size="lg"
              onClick={handleReset}
              disabled={resetMutation.isPending}
              className="h-12 px-8 border-dashed border-papaya-400 hover:bg-papaya-300/50 text-ink-400"
            >
              <RotateCcw className="w-4 h-4 mr-2" />
              Reset All
            </Button>
            <Button
              onClick={handleSave}
              disabled={!isDirty || updateMutation.isPending}
              className={cn("h-12 px-12 min-w-[200px] shadow-xl", isDirty ? theme.interactive.cta : "")}
            >
              {updateMutation.isPending ? (
                <Loader2 className="w-5 h-5 mr-2 animate-spin" />
              ) : (
                <Save className="w-5 h-5 mr-2" />
              )}
              {updateMutation.isPending ? 'Saving Registry...' : 'Save Registry'}
            </Button>
          </div>
        </div>
      </Card>
    </div>
  )
}
