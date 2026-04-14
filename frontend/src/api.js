import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  withCredentials: true,
})

// Override Content-Type only for JSON requests, not for FormData
api.interceptors.request.use((config) => {
  // Ensure headers object exists
  config.headers = config.headers || {}
  
  if (config.data instanceof FormData) {
    // Let the browser handle multipart/form-data
    delete config.headers['Content-Type']
  } else if (!config.headers['Content-Type'] && (config.data || config.method === 'post' || config.method === 'put')) {
    // Set JSON only for requests with data
    config.headers['Content-Type'] = 'application/json'
  }
  return config
})

// Log all requests for debugging
api.interceptors.request.use(
  (config) => {
    console.log(`[API] ${config.method.toUpperCase()} ${config.url}`)
    return config
  },
  (error) => Promise.reject(error)
)

// Log all responses for debugging
api.interceptors.response.use(
  (response) => {
    console.log(`[API] Response: ${response.status} ${response.statusText}`)
    return response
  },
  (error) => {
    console.error('[API] Error:', error.message)
    return Promise.reject(error)
  }
)

export default api

