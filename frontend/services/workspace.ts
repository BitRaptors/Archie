import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface WorkspaceRepository {
  repo_id: string
  name: string
  language: string | null
  analyzed_at: string | null
  has_structured: boolean
}

export interface ActiveRepository {
  active_repo_id: string | null
  repository: {
    id: string
    name: string
    language: string | null
  } | null
}

export interface AgentFiles {
  claude_md: string
  cursor_rules: string
  agents_md: string
}

export const workspaceService = {
  /** List all analyzed repositories with metadata. */
  async listRepositories(): Promise<WorkspaceRepository[]> {
    const response = await axios.get(`${API_URL}/api/v1/workspace/repositories`)
    return response.data
  },

  /** Get the currently active repository. */
  async getActive(): Promise<ActiveRepository> {
    const response = await axios.get(`${API_URL}/api/v1/workspace/active`)
    return response.data
  },

  /** Set the active repository. */
  async setActive(repoId: string): Promise<{ active_repo_id: string }> {
    const response = await axios.put(`${API_URL}/api/v1/workspace/active`, {
      repo_id: repoId,
    })
    return response.data
  },

  /** Clear the active repository. */
  async clearActive(): Promise<{ active_repo_id: null }> {
    const response = await axios.delete(`${API_URL}/api/v1/workspace/active`)
    return response.data
  },

  /** Get generated agent files for a repository. */
  async getAgentFiles(repoId: string): Promise<AgentFiles> {
    const response = await axios.get(
      `${API_URL}/api/v1/workspace/repositories/${repoId}/agent-files`
    )
    return response.data
  },

  /** Delete a repository analysis and its storage. */
  async deleteRepository(repoId: string): Promise<{ deleted: boolean }> {
    const response = await axios.delete(
      `${API_URL}/api/v1/workspace/repositories/${repoId}`
    )
    return response.data
  },
}
