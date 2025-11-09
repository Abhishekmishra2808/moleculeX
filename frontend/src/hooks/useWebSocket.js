import { useEffect, useRef, useState } from 'react'

export default function useWebSocket(jobId, onMessage) {
  const ws = useRef(null)
  const [isConnected, setIsConnected] = useState(false)
  const reconnectTimeoutRef = useRef(null)
  const mountedRef = useRef(true)
  const reconnectAttemptsRef = useRef(0)
  const jobCompletedRef = useRef(false)  // Track if job is complete
  const maxReconnectAttempts = 5

  useEffect(() => {
    if (!jobId) return

    mountedRef.current = true
    
    const connect = () => {
      if (!mountedRef.current) return
      
      // WebSocket URL - use environment variable or default
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
      // Convert HTTP(S) URL to WS(S) URL
      const wsUrl = apiUrl.replace(/^https?:\/\//, (match) => match === 'https://' ? 'wss://' : 'ws://') + `/ws/jobs/${jobId}`
      
      console.log('🔌 Connecting to WebSocket:', wsUrl)
      
      // Create WebSocket connection
      ws.current = new WebSocket(wsUrl)

      ws.current.onopen = () => {
        console.log('✅ WebSocket connected')
        setIsConnected(true)
        reconnectAttemptsRef.current = 0  // Reset reconnect counter on success
        
        // Send a ping every 30 seconds to keep connection alive
        const pingInterval = setInterval(() => {
          if (ws.current?.readyState === WebSocket.OPEN) {
            ws.current.send('ping')
          }
        }, 30000)
        
        ws.current.pingInterval = pingInterval
      }

      ws.current.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          
          // Handle ping/pong for keep-alive
          if (message.event_type === 'ping') {
            if (ws.current?.readyState === WebSocket.OPEN) {
              ws.current.send('pong')
            }
            return
          }
          
          // Check if job completed
          if (message.event_type === 'job_completed' || message.event_type === 'job_failed') {
            jobCompletedRef.current = true
            console.log(`✓ Job ${message.event_type}, stopping reconnection attempts`)
          }
          
          console.log('📨 WebSocket message:', message)
          if (onMessage) {
            onMessage(message)
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error)
        }
      }

      ws.current.onerror = (error) => {
        console.error('❌ WebSocket error:', error)
      }

      ws.current.onclose = (event) => {
        console.log('👋 WebSocket disconnected', { code: event.code, reason: event.reason })
        setIsConnected(false)
        
        // Clear ping interval
        if (ws.current?.pingInterval) {
          clearInterval(ws.current.pingInterval)
        }
        
        // Don't reconnect if job is complete or component unmounted
        if (jobCompletedRef.current) {
          console.log('✓ Job complete, not reconnecting')
          return
        }
        
        // Smart reconnection with exponential backoff
        if (mountedRef.current && reconnectAttemptsRef.current < maxReconnectAttempts) {
          // Special handling for normal browser close (code 1005 or 1006)
          if (event.code === 1005 || event.code === 1006) {
            console.log('ℹ️ Connection closed normally (browser/network), reconnecting...')
          }
          
          const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000)
          reconnectAttemptsRef.current++
          
          console.log(`🔄 Reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current}/${maxReconnectAttempts})`)
          
          reconnectTimeoutRef.current = setTimeout(() => {
            if (mountedRef.current && !jobCompletedRef.current) {
              connect()
            }
          }, delay)
        } else if (reconnectAttemptsRef.current >= maxReconnectAttempts) {
          console.error('❌ Max reconnection attempts reached')
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
      
      if (ws.current) {
        if (ws.current.pingInterval) {
          clearInterval(ws.current.pingInterval)
        }
        ws.current.close()
      }
    }
  }, [jobId]) // Remove onMessage from dependencies to prevent reconnection

  return { isConnected }
}
