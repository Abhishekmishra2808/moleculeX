import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import QueryCard from './components/QueryCard'
import AgentStatusRow from './components/AgentStatusRow'
import ResultsPanel from './components/ResultsPanel'
import ReportDownload from './components/ReportDownload'
import AnimatedBackground from './components/AnimatedBackground'
import Footer from './components/Footer'
import LandingPage from './components/landing/LandingPage'
import { submitQuery, getJobStatus, getJobResult } from './api/client'
import useSSE from './hooks/useSSE'

function App() {
  const [showLanding, setShowLanding] = useState(true)
  const [jobId, setJobId] = useState(null)
  const [query, setQuery] = useState('')
  const [isProcessing, setIsProcessing] = useState(false)
  const [agents, setAgents] = useState([])
  const [progress, setProgress] = useState(0)
  const [status, setStatus] = useState('idle')
  const [reportUrl, setReportUrl] = useState(null)
  const [results, setResults] = useState(null)
  const [isFetchingResults, setIsFetchingResults] = useState(false)

  const pollIntervalRef = useRef(null)
  const pollTimeoutRef = useRef(null)

  useSSE(jobId, (message) => {
    const { event_type, data } = message ?? {}

    switch (event_type) {
      case 'job_started':
        setIsProcessing(true)
        setStatus('running')
        break

      case 'progress_update':
        // Handle incremental progress updates
        if (data?.progress) setProgress(data.progress)
        if (data?.message) {
          console.log('📊 Progress:', data.message)
        }
        break

      case 'agent_update':
        setAgents((prev) => {
          const newAgents = [...prev]
          const idx = newAgents.findIndex((a) => a.name === data.agent)
          if (idx >= 0) {
            newAgents[idx] = {
              ...newAgents[idx],
              status: data.status,
              result_count: data.result_count || 0,
            }
          }
          return newAgents
        })
        break

      case 'job_completed': {
        console.log('🎉 Job completed, fetching results...')
        setStatus('completed')
        setIsProcessing(false)
        setProgress(100)
        if (data?.report_url) setReportUrl(data.report_url)
        const jId = data?.job_id ?? jobId
        clearPolling()
        // Fetch results immediately and wait for completion
        if (jId) {
          fetchResults(jId).then((resultData) => {
            if (resultData) {
              console.log('✅ Results fetched and displayed successfully')
            } else {
              console.warn('⚠️ No results returned, trying again in 2s...')
              setTimeout(() => fetchResults(jId), 2000)
            }
          }).catch(err => {
            console.error('❌ Error fetching results:', err)
            // Retry once
            setTimeout(() => fetchResults(jId), 2000)
          })
        }
        break
      }

      case 'job_failed':
        setStatus('failed')
        setIsProcessing(false)
        clearPolling()
        break

      default:
        break
    }
  })

  useEffect(() => {
    return () => clearPolling()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const clearPolling = () => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current)
      pollIntervalRef.current = null
    }
    if (pollTimeoutRef.current) {
      clearTimeout(pollTimeoutRef.current)
      pollTimeoutRef.current = null
    }
  }

  const fetchResults = async (jId) => {
    if (isFetchingResults) {
      console.log('⚠️ Already fetching results, skipping...')
      return
    }
    
    try {
      console.log('📥 Fetching results for job:', jId)
      setIsFetchingResults(true)
      const data = await getJobResult(jId)
      
      // Log data size for debugging
      const dataSize = JSON.stringify(data).length
      console.log('✅ Results received:', {
        size: `${(dataSize / 1024).toFixed(2)} KB`,
        trials: data.clinical_trials?.length || 0,
        patents: data.patents?.length || 0,
        literature: data.web_intel?.length || 0
      })
      
      setResults(data)
      if (data?.report_url) setReportUrl(data.report_url)
      return data
    } catch (err) {
      console.error('❌ Error fetching results:', err)
      // Don't throw, just log - this prevents the UI from breaking
    } finally {
      setIsFetchingResults(false)
    }
  }

  const handleSubmitQuery = async (userQuery) => {
    try {
      setQuery(userQuery)
      setIsProcessing(true)
      setStatus('queued')
      setProgress(0)
      setReportUrl(null)
      setResults(null)

      setAgents([
        { name: 'Master Agent', status: 'idle', result_count: 0 },
        { name: 'Clinical Trials Agent', status: 'idle', result_count: 0 },
        { name: 'Patent Agent', status: 'idle', result_count: 0 },
        { name: 'Web Intel Agent', status: 'idle', result_count: 0 },
      ])

      const response = await submitQuery(userQuery)
      const jId = response?.job_id
      if (!jId) throw new Error('submitQuery did not return job_id')
      setJobId(jId)
      clearPolling()
      pollProgress(jId)
      setShowLanding(false)
    } catch (err) {
      console.error('Error submitting query:', err)
      setIsProcessing(false)
      setStatus('failed')
    }
  }

  const pollProgress = (jId) => {
    pollIntervalRef.current = setInterval(async () => {
      try {
        const data = await getJobStatus(jId)
        if (!data) return
        if (typeof data.progress === 'number') setProgress(data.progress)
        if (Array.isArray(data.agents)) setAgents(data.agents)
        if (data.status) setStatus(data.status)

        if (data.status === 'completed') {
          console.log('📊 Polling detected job completion')
          clearPolling()
          setIsProcessing(false)
          setProgress(100)
          // Fetch results immediately - this is the backup mechanism
          if (!results) {  // Only fetch if not already loaded by SSE
            console.log('📥 Polling triggering result fetch...')
            await fetchResults(jId)
          } else {
            console.log('✓ Results already loaded via SSE')
          }
        } else if (data.status === 'failed') {
          clearPolling()
          setIsProcessing(false)
          setStatus('failed')
        }
      } catch (err) {
        console.error('Error polling progress:', err)
      }
    }, 2000)

    pollTimeoutRef.current = setTimeout(() => {
      clearPolling()
    }, 300000) // 5 minutes
  }

  const handleReset = () => {
    clearPolling()
    setShowLanding(true)
    setJobId(null)
    setQuery('')
    setIsProcessing(false)
    setAgents([])
    setProgress(0)
    setStatus('idle')
    setReportUrl(null)
    setResults(null)
    setIsFetchingResults(false)
  }

  const scrollToQuery = () => {
    const el = document.getElementById('query-section')
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  return (
    <div className="min-h-screen relative">
      {/* Backgrounds */}
      {status === 'idle' && (
        <div className="fixed inset-0 -z-10">
          <div className="absolute inset-0 bg-gradient-to-br from-indigo-50 via-purple-50 to-pink-50" />
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_50%,rgba(120,119,198,0.3),transparent_50%)]" />
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_80%_80%,rgba(139,92,246,0.3),transparent_50%)]" />
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_40%_80%,rgba(236,72,153,0.2),transparent_50%)]" />
          <div className="absolute inset-0 backdrop-blur-3xl" />
        </div>
      )}

      {(isProcessing || status === 'completed') && <AnimatedBackground />}

      {(isProcessing || status === 'completed') && (
        <motion.nav
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="fixed top-0 left-0 right-0 z-50 backdrop-blur-xl bg-white/70 border-b border-purple-100/50 shadow-lg"
        >
          <div className="max-w-7xl mx-auto px-6 py-4">
            <div className="flex items-center justify-between">
              <button
                onClick={handleReset}
                className="flex items-center gap-3 hover:opacity-80 transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-purple-500/30 rounded-xl px-3 py-2 group"
              >
                <div className="relative">
                  <div className="absolute inset-0 bg-gradient-to-r from-purple-400 to-pink-400 rounded-lg blur-md opacity-50 group-hover:opacity-70 transition-opacity" />
                  <span className="relative text-3xl">🧬</span>
                </div>
                <div className="flex flex-col items-start">
                  <span className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-indigo-600 to-purple-600">
                    MoleculeX
                  </span>
                  <span className="text-xs text-gray-500">AI Intelligence</span>
                </div>
              </button>

              <div className="flex items-center gap-4">
                {isProcessing && (
                  <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-purple-50 to-pink-50 rounded-full border border-purple-200">
                    <motion.div animate={{ rotate: 360 }} transition={{ duration: 2, repeat: Infinity, ease: 'linear' }} className="w-3 h-3 border-2 border-purple-500 border-t-transparent rounded-full" />
                    <span className="text-sm font-semibold text-purple-700">Analyzing...</span>
                  </motion.div>
                )}

                {status === 'completed' && (
                  <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-green-50 to-emerald-50 rounded-full border border-green-200">
                    <span className="text-green-600">✓</span>
                    <span className="text-sm font-semibold text-green-700">Complete</span>
                  </motion.div>
                )}

                {status === 'completed' && (
                  <motion.button initial={{ scale: 0 }} animate={{ scale: 1 }} whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} onClick={handleReset} className="px-5 py-2 bg-gradient-to-r from-indigo-600 to-purple-600 text-white font-semibold rounded-full shadow-lg hover:shadow-xl transition-all duration-300">
                    + New Analysis
                  </motion.button>
                )}
              </div>
            </div>
          </div>
        </motion.nav>
      )}

      <div className="relative z-10">
        <AnimatePresence mode="wait">
          {status === 'idle' && (
            <motion.section
              key="hero"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0, y: -30 }}
              transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
              className="min-h-screen flex flex-col items-center justify-center px-6 relative"
            >
              {/* hero content (kept as your original) */}
              <div className="absolute inset-0 overflow-hidden pointer-events-none opacity-30">
                {[...Array(8)].map((_, i) => (
                  <motion.div
                    key={i}
                    className="absolute w-3 h-3 bg-gradient-to-br from-purple-400 to-pink-400 rounded-full"
                    style={{ left: `${Math.random() * 100}%`, top: `${Math.random() * 100}%` }}
                    animate={{ y: [0, -30, 0], x: [0, Math.random() * 20 - 10, 0], scale: [1, 1.2, 1], opacity: [0.3, 0.6, 0.3] }}
                    transition={{ duration: 4 + Math.random() * 2, repeat: Infinity, delay: Math.random() * 2 }}
                  />
                ))}
              </div>

              <motion.div initial={{ scale: 0.9, opacity: 0, y: 20 }} animate={{ scale: 1, opacity: 1, y: 0 }} transition={{ delay: 0.2, duration: 0.8 }} className="text-center max-w-4xl mx-auto relative z-10">
                {/* trimmed hero content for brevity — keep your existing JSX here */}
                <div className="mb-10"> {/* svg + logo block (copy from original) */} </div>
                <h1 className="text-7xl md:text-8xl font-bold mb-6 tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600">MoleculeX</h1>
                <p className="text-2xl md:text-3xl text-gray-800 font-semibold mb-5">AI-Powered Pharmaceutical Intelligence</p>
                <p className="text-lg md:text-xl text-gray-600 max-w-3xl mx-auto leading-relaxed mb-8">Unlock breakthrough insights with advanced AI analysis of clinical trials, patent landscapes, and scientific literature—all unified in one powerful platform</p>

                <div className="flex flex-wrap items-center justify-center gap-4 mb-12">
                  {[
                    { icon: '🧪', text: 'Clinical Trials' },
                    { icon: '📋', text: 'Patent Analysis' },
                    { icon: '📚', text: 'Literature Review' },
                    { icon: '🤖', text: 'AI-Powered' },
                  ].map((b, i) => (
                    <div key={i} className="flex items-center gap-2 px-4 py-2 bg-white/80 backdrop-blur-sm rounded-full shadow-lg border border-purple-100">
                      <span className="text-xl">{b.icon}</span>
                      <span className="text-sm font-medium text-gray-700">{b.text}</span>
                    </div>
                  ))}
                </div>

                <button onClick={scrollToQuery} className="group relative inline-flex items-center gap-3 px-12 py-5 text-xl font-bold text-white rounded-full overflow-hidden shadow-2xl transition-all duration-300 focus:outline-none focus:ring-4 focus:ring-purple-500/40">
                  <div className="absolute inset-0 bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 transition-transform group-hover:scale-110" />
                  <span className="relative">Start Analysis</span>
                </button>

                <div className="mt-16 flex items-center justify-center gap-12">
                  {[
                    { value: '1000+', label: 'Trials Analyzed' },
                    { value: '500+', label: 'Patents Reviewed' },
                    { value: '99.9%', label: 'Accuracy' },
                  ].map((s, i) => (
                    <div key={i} className="text-center">
                      <div className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-purple-600 to-pink-600">{s.value}</div>
                      <div className="text-sm text-gray-600 mt-1">{s.label}</div>
                    </div>
                  ))}
                </div>
              </motion.div>
            </motion.section>
          )}
        </AnimatePresence>

        <section id="query-section" className="bg-section-gradient py-16 px-6">
          <div className="max-w-5xl mx-auto w-full">
            <AnimatePresence mode="wait">{status === 'idle' && <QueryCard onSubmit={handleSubmitQuery} />}</AnimatePresence>
          </div>
        </section>

        {(isProcessing || status === 'completed') && (
          <div className={`${isProcessing || status === 'completed' ? 'pt-20' : ''} bg-white`}>
            <div className="max-w-screen-2xl mx-auto w-[95%]">
              <div className="grid lg:grid-cols-12 gap-8 py-12">
                <div className="lg:col-span-5 space-y-6">
                  <div className="lg:sticky lg:top-24 space-y-6">
                    <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} className="backdrop-blur-glass bg-white/70 rounded-3xl shadow-apple border border-white/30 p-8">
                      <h3 className="text-sm font-semibold text-apple-gray-500 uppercase tracking-wider mb-3">Your Query</h3>
                      <p className="text-lg text-apple-gray-800 font-medium leading-relaxed mb-6">{query}</p>

                      {isProcessing && (
                        <div>
                          <div className="flex items-center justify-between mb-3">
                            <span className="text-sm font-medium text-apple-gray-600">Analysis Progress</span>
                            <span className="text-sm font-semibold text-apple-lavender-500">{progress}%</span>
                          </div>
                          <div className="w-full bg-apple-gray-200/50 rounded-full h-2 overflow-hidden backdrop-blur-sm">
                            <motion.div className="bg-gradient-to-r from-apple-lavender-400 to-apple-lavender-500 h-full rounded-full relative overflow-hidden" initial={{ width: 0 }} animate={{ width: `${progress}%` }} transition={{ duration: 0.5, ease: 'easeOut' }}>
                              <motion.div className="absolute inset-0 bg-shimmer-gradient" animate={{ backgroundPosition: ['200% 0', '-200% 0'] }} transition={{ duration: 2, repeat: Infinity, ease: 'linear' }} style={{ backgroundSize: '200% 100%' }} />
                            </motion.div>
                          </div>
                        </div>
                      )}

                      {status === 'completed' && <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} onClick={handleReset} className="w-full px-6 py-3 backdrop-blur-sm bg-apple-gray-800/90 hover:bg-apple-gray-900 text-white rounded-2xl transition-all duration-300 shadow-apple font-medium">New Analysis</motion.button>}
                    </motion.div>

                    <AgentStatusRow agents={agents} />
                  </div>
                </div>

                <div className="lg:col-span-7">
                  <div className="space-y-6">
                    {status === 'completed' && !results && isFetchingResults && (
                      <motion.div 
                        initial={{ opacity: 0 }} 
                        animate={{ opacity: 1 }}
                        className="backdrop-blur-glass bg-white/70 rounded-3xl shadow-apple border border-white/30 p-8"
                      >
                        <div className="flex items-center justify-center gap-3">
                          <motion.div 
                            animate={{ rotate: 360 }} 
                            transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                            className="w-6 h-6 border-3 border-purple-500 border-t-transparent rounded-full"
                          />
                          <span className="text-lg font-medium text-gray-700">Loading results...</span>
                        </div>
                      </motion.div>
                    )}
                    {status === 'completed' && !results && !isFetchingResults && (
                      <motion.div 
                        initial={{ opacity: 0 }} 
                        animate={{ opacity: 1 }}
                        className="backdrop-blur-glass bg-white/70 rounded-3xl shadow-apple border border-white/30 p-8"
                      >
                        <div className="text-center">
                          <p className="text-lg font-medium text-gray-700 mb-4">⚠️ Results not loaded yet</p>
                          <button 
                            onClick={() => fetchResults(jobId)}
                            className="px-6 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition"
                          >
                            Retry Loading Results
                          </button>
                        </div>
                      </motion.div>
                    )}
                    {results && <ResultsPanel results={results} />}
                    {reportUrl && <ReportDownload reportUrl={reportUrl} jobId={jobId} />}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {(status === 'idle' || status === 'completed') && <Footer />}
      </div>
    </div>
  )
}

export default App
