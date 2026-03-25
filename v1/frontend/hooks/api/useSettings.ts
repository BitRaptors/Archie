import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { settingsService, LibraryCapabilityInput } from '@/services/settings'

const KEYS = {
  ignoredDirs: ['settings', 'ignored-dirs'] as const,
  libraryCaps: ['settings', 'library-capabilities'] as const,
  ecosystemOptions: ['settings', 'ecosystem-options'] as const,
  capabilityOptions: ['settings', 'capability-options'] as const,
}

/** Fetch all ignored directories. */
export function useIgnoredDirs() {
  return useQuery({
    queryKey: KEYS.ignoredDirs,
    queryFn: () => settingsService.listIgnoredDirs(),
    staleTime: 60_000,
  })
}

/** Replace all ignored directories. */
export function useUpdateIgnoredDirs() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (directories: string[]) => settingsService.updateIgnoredDirs(directories),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.ignoredDirs })
    },
  })
}

/** Reset ignored directories to defaults. */
export function useResetIgnoredDirs() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => settingsService.resetIgnoredDirs(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.ignoredDirs })
    },
  })
}

/** Fetch the predefined list of valid ecosystem values. */
export function useEcosystemOptions() {
  return useQuery({
    queryKey: KEYS.ecosystemOptions,
    queryFn: () => settingsService.getEcosystemOptions(),
    staleTime: Infinity,
  })
}

/** Fetch the predefined list of valid capability values. */
export function useCapabilityOptions() {
  return useQuery({
    queryKey: KEYS.capabilityOptions,
    queryFn: () => settingsService.getCapabilityOptions(),
    staleTime: Infinity,
  })
}

/** Fetch all library capabilities. */
export function useLibraryCapabilities() {
  return useQuery({
    queryKey: KEYS.libraryCaps,
    queryFn: () => settingsService.listLibraryCapabilities(),
    staleTime: 60_000,
  })
}

/** Replace all library capabilities. */
export function useUpdateLibraryCapabilities() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (libraries: LibraryCapabilityInput[]) =>
      settingsService.updateLibraryCapabilities(libraries),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.libraryCaps })
    },
  })
}

/** Reset library capabilities to defaults. */
export function useResetLibraryCapabilities() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => settingsService.resetLibraryCapabilities(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.libraryCaps })
    },
  })
}

/** Reset all data — wipe DB rows, re-seed settings, clear storage. */
export function useResetAllData() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => settingsService.resetAllData(),
    onSuccess: () => {
      qc.invalidateQueries()
    },
  })
}
