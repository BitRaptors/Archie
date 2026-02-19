import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface IgnoredDirectory {
  id: string
  directory_name: string
  created_at: string | null
}

export interface LibraryCapability {
  id: string
  library_name: string
  ecosystem: string
  capabilities: string[]
  created_at: string | null
  updated_at: string | null
}

export interface LibraryCapabilityInput {
  library_name: string
  ecosystem: string
  capabilities: string[]
}

export const settingsService = {
  // ── Ignored Directories ──────────────────────────────────────
  async listIgnoredDirs(): Promise<IgnoredDirectory[]> {
    const response = await axios.get(`${API_URL}/api/v1/settings/ignored-dirs`)
    return response.data
  },

  async updateIgnoredDirs(directories: string[]): Promise<IgnoredDirectory[]> {
    const response = await axios.put(`${API_URL}/api/v1/settings/ignored-dirs`, { directories })
    return response.data
  },

  async resetIgnoredDirs(): Promise<IgnoredDirectory[]> {
    const response = await axios.post(`${API_URL}/api/v1/settings/ignored-dirs/reset`)
    return response.data
  },

  // ── Library Capabilities ─────────────────────────────────────
  async getEcosystemOptions(): Promise<string[]> {
    const response = await axios.get(`${API_URL}/api/v1/settings/ecosystem-options`)
    return response.data
  },

  async getCapabilityOptions(): Promise<string[]> {
    const response = await axios.get(`${API_URL}/api/v1/settings/capability-options`)
    return response.data
  },

  async listLibraryCapabilities(): Promise<LibraryCapability[]> {
    const response = await axios.get(`${API_URL}/api/v1/settings/library-capabilities`)
    return response.data
  },

  async updateLibraryCapabilities(libraries: LibraryCapabilityInput[]): Promise<LibraryCapability[]> {
    const response = await axios.put(`${API_URL}/api/v1/settings/library-capabilities`, { libraries })
    return response.data
  },

  async resetLibraryCapabilities(): Promise<LibraryCapability[]> {
    const response = await axios.post(`${API_URL}/api/v1/settings/library-capabilities/reset`)
    return response.data
  },
}
