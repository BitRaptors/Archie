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
  
  async analyze(owner: string, repo: string, token: string, promptConfig?: Record<string, string>) {
    const response = await axios.post(
      `${API_URL}/api/v1/repositories/${owner}/${repo}/analyze`,
      { prompt_config: promptConfig },
      { headers: authHeaders(token) }
    )
    return response.data
  },
}

