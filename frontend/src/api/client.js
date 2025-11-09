import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

export const submitQuery = async (query) => {
  const response = await api.post('/api/query', { query })
  return response.data
}

export const getJobStatus = async (jobId) => {
  const response = await api.get(`/api/status/${jobId}`)
  return response.data
}

export const getJobResult = async (jobId) => {
  const response = await api.get(`/api/result/${jobId}`)
  return response.data
}

export default api
