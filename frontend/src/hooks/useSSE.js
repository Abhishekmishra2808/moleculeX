import { useEffect, useRef, useState } from 'react'

export default function useSSE(jobId, onMessage) {
  const eventSourceRef = useRef(null)
  const [isConnected, setIsConnected] = useState(false)
  const reconnectTimeoutRef = useRef(null)
  const mountedRef = useRef(true)
  const reconnectAttemptsRef = useRef(0)
  const jobCompletedRef = useRef(false)
  const maxReconnectAttempts = 5

  useEffect(() => {
    if (!jobId) return

    mountedRef.current = true
    reconnectAttemptsRef.current = 0
    jobCompletedRef.current = false

    const connect = () => {
      if (!mountedRef.current || jobCompletedRef.current) return

      // SSE URL
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
      const sseUrl = `${apiUrl}/api/stream/${jobId}`

      console.log('🔌 Connecting to SSE:', sseUrl)

      // Create EventSource connection
      eventSourceRef.current = new EventSource(sseUrl)

      eventSourceRef.current.onopen = () => {
        console.log('✅ SSE connected')
        setIsConnected(true)
        reconnectAttemptsRef.current = 0 // Reset on successful connection
      }

      eventSourceRef.current.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          console.log('📨 SSE message:', message)

          // Check if job completed
          if (message.event_type === 'job_completed' || message.event_type === 'job_failed') {
            jobCompletedRef.current = true
            console.log(`✓ Job ${message.event_type}, SSE will close`)
          }

          if (onMessage) {
            onMessage(message)
          }
        } catch (error) {
          console.error('Error parsing SSE message:', error)
        }
      }

      eventSourceRef.current.onerror = (error) => {
        console.log('⚠️ SSE connection closed/error')
        setIsConnected(false)

        // Close the failed connection
        if (eventSourceRef.current) {
          eventSourceRef.current.close()
          eventSourceRef.current = null
        }

        // Don't reconnect if job is complete
        if (jobCompletedRef.current) {
          console.log('✓ Job complete, SSE closed normally - not reconnecting')
          return
        }

        // Don't reconnect immediately - might be normal server close
        // Only reconnect if we haven't reached max attempts
        if (mountedRef.current && reconnectAttemptsRef.current < maxReconnectAttempts) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000)
          reconnectAttemptsRef.current++

          console.log(`ℹ️ SSE disconnected, will retry in ${delay}ms (attempt ${reconnectAttemptsRef.current}/${maxReconnectAttempts})`)

          reconnectTimeoutRef.current = setTimeout(() => {
            if (mountedRef.current && !jobCompletedRef.current) {
              console.log('🔄 Attempting SSE reconnection...')
              connect()
            }
          }, delay)
        } else if (reconnectAttemptsRef.current >= maxReconnectAttempts) {
          console.log('ℹ️ Max reconnection attempts reached, stopping')
        }
      }
    }

    connect()

    // Cleanup on unmount
    return () => {
      mountedRef.current = false

      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }

      if (eventSourceRef.current) {
        eventSourceRef.current.close()
        eventSourceRef.current = null
      }
    }
  }, [jobId])

  return { isConnected }
}
