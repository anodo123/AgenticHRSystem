import axios from 'axios'
import { useAuthStore } from '../store/auth'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api/v1',
  timeout: 15_000,
})

api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken
  if (token) config.headers.Authorization = `Bearer ${token}`
  config.headers['X-Correlation-ID'] = crypto.randomUUID()
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const request = error.config
    const auth = useAuthStore.getState()
    if (error.response?.status === 401 && auth.refreshToken && !request?._retried) {
      request._retried = true
      try {
        const response = await axios.post(`${api.defaults.baseURL}/auth/refresh`, {
          refresh_token: auth.refreshToken,
        })
        auth.setAccessToken(response.data.access_token)
        request.headers.Authorization = `Bearer ${response.data.access_token}`
        return api(request)
      } catch {
        auth.logout()
      }
    }
    return Promise.reject(error)
  },
)

export function errorMessage(error: unknown) {
  if (axios.isAxiosError(error)) return error.response?.data?.detail || error.message
  return error instanceof Error ? error.message : 'Something went wrong'
}
