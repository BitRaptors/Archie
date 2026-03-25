import axios from 'axios'
import { SERVER_TOKEN } from '@/context/auth'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

/** Build headers — skip Authorization when using server-side token. */
function authHeaders(token: string): Record<string, string> {
  if (token === SERVER_TOKEN) return {}
  return { Authorization: `Bearer ${token}` }
}

export const repositoriesService = {
  async list(token: string) {
    const response = await axios.get(`${API_URL}/api/v1/repositories/`, {
      headers: authHeaders(token),
    })
    return response.data
  },

  async get(id: string, token: string) {
    const response = await axios.get(`${API_URL}/api/v1/repositories/${id}`, {
      headers: authHeaders(token),
    })
    return response.data
  },

  async analyze(owner: string, repo: string, token: string, mode: string = 'full', promptConfig?: Record<string, string>) {
    const response = await axios.post(
      `${API_URL}/api/v1/repositories/${owner}/${repo}/analyze`,
      { prompt_config: promptConfig, mode },
      { headers: authHeaders(token) }
    )
    return response.data
  },

  async getLatestCommitSha(owner: string, repo: string, token: string) {
    const response = await axios.get(`${API_URL}/api/v1/repositories/${owner}/${repo}/latest-commit`, {
      headers: authHeaders(token),
    })
    return response.data.sha
  },

  async validateLocalPath(path: string) {
    const response = await axios.post(`${API_URL}/api/v1/repositories/local/validate`, { path })
    return response.data as { valid: boolean; name: string | null; is_git_repo: boolean; error?: string }
  },

  async analyzeLocal(localPath: string, mode: string = 'full', promptConfig?: Record<string, string>) {
    const response = await axios.post(`${API_URL}/api/v1/repositories/local/analyze`, {
      local_path: localPath,
      mode,
      prompt_config: promptConfig,
    })
    return response.data
  },

  async pickFolder() {
    const response = await axios.get(`${API_URL}/api/v1/system/pick-folder`)
    return response.data as { path: string | null; error?: string }
  },
}

