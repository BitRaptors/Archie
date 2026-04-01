import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface AuthConfig {
  server_token_configured: boolean
}

export const authService = {
  /** Check if the backend has a GITHUB_TOKEN configured in its env. */
  async getConfig(): Promise<AuthConfig> {
    const response = await axios.get(`${API_URL}/api/v1/auth/config`)
    return response.data
  },

  async authenticate(token: string) {
    const response = await axios.post(
      `${API_URL}/api/v1/auth/github`,
      { token },
      {
        headers: { 'Content-Type': 'application/json' },
      }
    )
    return response.data
  },

  async getStatus() {
    const response = await axios.get(`${API_URL}/api/v1/auth/status`)
    return response.data
  },

  async logout() {
    const response = await axios.delete(`${API_URL}/api/v1/auth/`)
    return response.data
  },
}


