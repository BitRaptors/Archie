import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const repositoriesService = {
  async list(token: string) {
    const response = await axios.get(`${API_URL}/api/v1/repositories/`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    return response.data
  },
  
  async get(id: string, token: string) {
    const response = await axios.get(`${API_URL}/api/v1/repositories/${id}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    return response.data
  },
  
  async analyze(owner: string, repo: string, token: string, promptConfig?: Record<string, string>) {
    const response = await axios.post(
      `${API_URL}/api/v1/repositories/${owner}/${repo}/analyze`,
      { prompt_config: promptConfig },
      { headers: { Authorization: `Bearer ${token}` } }
    )
    return response.data
  },
}

