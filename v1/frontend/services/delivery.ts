import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface DeliveryRequest {
  source_repo_id: string
  target_repo?: string
  strategy: 'pr' | 'commit' | 'local'
  outputs: string[]
  branch_prefix?: string
  target_local_path?: string
}

export interface DeliveryResult {
  status: string
  strategy: string
  pr_url: string | null
  commit_sha: string | null
  branch: string | null
  files_delivered: string[]
}

export const deliveryService = {
  /** Push architecture outputs to a target GitHub repository. */
  async apply(req: DeliveryRequest, token?: string): Promise<DeliveryResult> {
    const headers: Record<string, string> = {}
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }
    const response = await axios.post(`${API_URL}/api/v1/delivery/apply`, req, {
      headers,
    })
    return response.data
  },
}
