import { motion } from 'framer-motion'
import { useState, useEffect } from 'react'

export default function ResultsPanel({ results }) {
  const { 
    executive_summary, 
    key_findings, 
    clinical_trials, 
    patents, 
    web_intel,
    confidence_score = 0,
    confidence_level = "Medium"
  } = results

  // Performance monitoring
  useEffect(() => {
    console.log('🎨 ResultsPanel rendering with:', {
      trials: clinical_trials?.length || 0,
      patents: patents?.length || 0,
      literature: web_intel?.length || 0
    })
  }, [clinical_trials, patents, web_intel])

  const [expandedSections, setExpandedSections] = useState({
    summary: true,
    trials: true,
    patents: true,
    literature: true,
  })

  const [showConfidenceExplainer, setShowConfidenceExplainer] = useState(false)

  const toggleSection = (section) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }))
  }

  // Calculate key metrics
  const keyMetrics = {
    trials: clinical_trials?.length || 0,
    patents: patents?.length || 0,
    literature: web_intel?.length || 0,
    phase3Trials: clinical_trials?.filter(t => t.phase?.includes('3') || t.phase?.includes('4')).length || 0
  }

  // Confidence explainability
  const getConfidenceExplanation = () => {
    const explanations = []
    if (keyMetrics.phase3Trials > 0) {
      explanations.push(`${keyMetrics.phase3Trials} Phase 3/4 clinical trial${keyMetrics.phase3Trials > 1 ? 's' : ''}`)
    }
    if (keyMetrics.trials > 0) {
      explanations.push(`${keyMetrics.trials} total clinical trial${keyMetrics.trials > 1 ? 's' : ''}`)
    }
    if (keyMetrics.patents > 0) {
      explanations.push(`${keyMetrics.patents} related patent${keyMetrics.patents > 1 ? 's' : ''}`)
    }
    if (keyMetrics.literature > 0) {
      explanations.push(`${keyMetrics.literature} scientific publication${keyMetrics.literature > 1 ? 's' : ''}`)
    }
    return explanations.join(', ')
  }

  // Apple-style confidence badge
  const getConfidenceBadge = (level) => {
    const badges = {
      "High": { 
        bg: "bg-apple-mint-100/80", 
        text: "text-apple-mint-700", 
        ring: "ring-apple-mint-300",
        glow: "shadow-glow-mint"
      },
      "Medium": { 
        bg: "bg-apple-amber-100/80", 
        text: "text-apple-amber-700", 
        ring: "ring-apple-amber-300",
        glow: ""
      },
      "Low": { 
        bg: "bg-red-100/80", 
        text: "text-red-700", 
        ring: "ring-red-300",
        glow: ""
      }
    }
    return badges[level] || badges["Medium"]
  }

  const confidenceBadge = getConfidenceBadge(confidence_level)

  // Match score styling
  const getMatchScoreStyle = (score) => {
    if (score >= 0.8) return "text-apple-mint-600 font-semibold"
    if (score >= 0.6) return "text-apple-lavender-600 font-semibold"
    if (score >= 0.4) return "text-apple-amber-600 font-medium"
    return "text-apple-gray-500 font-medium"
  }

  const getPhaseStyle = (phase) => {
    if (!phase) {
      return "bg-apple-gray-100/80 text-apple-gray-700 ring-1 ring-apple-gray-300/50"
    }
    if (phase.includes('3') || phase.includes('4')) {
      return "bg-apple-mint-100/80 text-apple-mint-700 ring-1 ring-apple-mint-300/50"
    }
    if (phase.includes('2')) {
      return "bg-apple-lavender-100/80 text-apple-lavender-700 ring-1 ring-apple-lavender-300/50"
    }
    return "bg-apple-gray-100/80 text-apple-gray-700 ring-1 ring-apple-gray-300/50"
  }

  return (
    <div className="space-y-6">
      {/* Sticky Header - Translucent Blur */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="backdrop-blur-strong bg-white/80 rounded-3xl shadow-apple-lg border border-white/40 px-8 py-6"
      >
        <div className="flex items-center justify-between flex-wrap gap-6">
          <div>
            <h2 className="text-title font-display text-apple-gray-800">Analysis Complete</h2>
            <p className="text-sm text-apple-gray-600 mt-1">Comprehensive insights from multiple intelligence sources</p>
          </div>
          
          {/* Circular Confidence Score + Key Metrics */}
          <div className="flex items-center gap-8">
            {/* Key Metrics Box */}
            <div className="grid grid-cols-2 gap-4">
              <div className="backdrop-blur-sm bg-apple-mint-50/50 px-4 py-2 rounded-xl border border-apple-mint-200/30">
                <div className="text-2xl font-bold text-apple-mint-600">{keyMetrics.trials}</div>
                <div className="text-xs text-apple-gray-600 font-medium">Trials</div>
              </div>
              <div className="backdrop-blur-sm bg-apple-lavender-50/50 px-4 py-2 rounded-xl border border-apple-lavender-200/30">
                <div className="text-2xl font-bold text-apple-lavender-600">{keyMetrics.patents}</div>
                <div className="text-xs text-apple-gray-600 font-medium">Patents</div>
              </div>
              <div className="backdrop-blur-sm bg-apple-gray-50/50 px-4 py-2 rounded-xl border border-apple-gray-200/30 col-span-2">
                <div className="text-2xl font-bold text-apple-gray-700">{keyMetrics.literature}</div>
                <div className="text-xs text-apple-gray-600 font-medium">Publications</div>
              </div>
            </div>

            {/* Confidence Score with Explainer */}
            <div className="relative">
              <div className="relative">
                <svg className="w-24 h-24 -rotate-90" viewBox="0 0 100 100">
                  {/* Background ring */}
                  <circle
                    cx="50"
                    cy="50"
                    r="42"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="6"
                    className="stroke-apple-gray-200/50"
                  />
                  
                  {/* Progress ring */}
                  <motion.circle
                    cx="50"
                    cy="50"
                    r="42"
                    fill="none"
                    strokeWidth="6"
                    strokeLinecap="round"
                    className={`${
                      confidence_level === 'High' ? 'stroke-apple-mint-500' :
                      confidence_level === 'Medium' ? 'stroke-apple-amber-400' :
                      'stroke-red-400'
                    } ${confidenceBadge.glow}`}
                    initial={{ strokeDasharray: '0 264' }}
                    animate={{ strokeDasharray: `${(confidence_score / 100) * 264} 264` }}
                    transition={{ duration: 1.5, delay: 0.5, ease: [0.22, 1, 0.36, 1] }}
                  />
                </svg>
                
                {/* Center content */}
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <motion.span 
                    className="text-2xl font-bold text-apple-gray-800"
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={{ delay: 0.8, duration: 0.3 }}
                  >
                    {Math.round(confidence_score)}
                  </motion.span>
                  <span className="text-xs text-apple-gray-500 font-medium">Score</span>
                </div>

                {/* Info button */}
                <button
                  onClick={() => setShowConfidenceExplainer(!showConfidenceExplainer)}
                  className="absolute -bottom-2 -right-2 w-6 h-6 rounded-full backdrop-blur-sm bg-apple-gray-700/90 text-white flex items-center justify-center hover:bg-apple-gray-800 transition-colors text-xs font-bold"
                  aria-label="Explain confidence score"
                >
                  ?
                </button>
              </div>
              
              {/* Confidence Badge */}
              <div className={`mt-3 ${confidenceBadge.bg} ${confidenceBadge.text} px-4 py-1.5 rounded-full ${confidenceBadge.ring} ring-1 backdrop-blur-sm text-center`}>
                <span className="font-semibold text-sm">{confidence_level}</span>
              </div>

              {/* Explainer Tooltip */}
              {showConfidenceExplainer && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.9, y: -10 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.9 }}
                  className="absolute top-full right-0 mt-2 w-72 backdrop-blur-strong bg-white/95 rounded-2xl shadow-apple-lg border border-white/40 p-4 z-30"
                >
                  <div className="flex items-start gap-2 mb-2">
                    <svg className="w-5 h-5 text-apple-lavender-500 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <div>
                      <h4 className="text-sm font-semibold text-apple-gray-800 mb-1">Confidence Explanation</h4>
                      <p className="text-xs text-apple-gray-600 leading-relaxed">
                        {getConfidenceExplanation()}
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => setShowConfidenceExplainer(false)}
                    className="text-xs text-apple-lavender-600 hover:text-apple-lavender-700 font-medium"
                  >
                    Got it
                  </button>
                </motion.div>
              )}
            </div>
          </div>
        </div>
      </motion.div>

      {/* Executive Summary - Two Column Layout */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2, duration: 0.5 }}
        className="backdrop-blur-glass bg-white/70 rounded-3xl shadow-apple border border-white/30 overflow-hidden"
      >
        <button
          onClick={() => toggleSection('summary')}
          className="w-full px-8 py-6 flex items-center justify-between hover:bg-white/50 transition-colors focus:outline-none focus:bg-white/50 focus:ring-2 focus:ring-inset focus:ring-apple-lavender-300"
          aria-expanded={expandedSections.summary}
          aria-label="Toggle executive summary section"
        >
          <div className="flex items-center gap-3">
            <span className="text-2xl">📊</span>
            <h3 className="text-xl font-semibold text-apple-gray-800">Executive Summary</h3>
          </div>
          <motion.svg
            className="w-6 h-6 text-apple-gray-500"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            animate={{ rotate: expandedSections.summary ? 180 : 0 }}
            transition={{ duration: 0.3 }}
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </motion.svg>
        </button>
        
        {expandedSections.summary && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="px-8 pb-8"
          >
            <div className="bg-apple-lavender-50/50 backdrop-blur-sm border border-apple-lavender-200/30 p-6 rounded-2xl">
              <p className="text-apple-gray-700 leading-relaxed">{executive_summary}</p>
            </div>
            
            {/* Key Findings */}
            <div className="mt-6">
              <h4 className="text-sm font-semibold text-apple-gray-500 uppercase tracking-wider mb-4">
                Key Findings
              </h4>
              <div className="space-y-3">
                {key_findings.map((finding, index) => (
                  <motion.div
                    key={index}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.3 + index * 0.05 }}
                    className="flex items-start gap-3 backdrop-blur-sm bg-white/40 p-4 rounded-xl border border-apple-gray-200/30"
                  >
                    <span className="text-apple-mint-500 text-lg flex-shrink-0 mt-0.5">✓</span>
                    <p className="text-apple-gray-700 text-sm leading-relaxed">{finding}</p>
                  </motion.div>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </motion.div>

      {/* Clinical Trials - Card Grid */}
      {clinical_trials.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3, duration: 0.5 }}
          className="backdrop-blur-glass bg-white/70 rounded-3xl shadow-apple border border-white/30 overflow-hidden"
        >
          <button
            onClick={() => toggleSection('trials')}
            className="w-full px-8 py-6 flex items-center justify-between hover:bg-white/50 transition-colors focus:outline-none focus:bg-white/50 focus:ring-2 focus:ring-inset focus:ring-apple-lavender-300"
            aria-expanded={expandedSections.trials}
            aria-label="Toggle clinical trials section"
          >
            <div className="flex items-center gap-3">
              <span className="text-2xl">🔬</span>
              <h3 className="text-xl font-semibold text-apple-gray-800">
                Clinical Trials
                <span className="ml-2 text-apple-gray-500 font-normal text-base">({clinical_trials.length})</span>
              </h3>
            </div>
            <motion.svg
              className="w-6 h-6 text-apple-gray-500"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              animate={{ rotate: expandedSections.trials ? 180 : 0 }}
              transition={{ duration: 0.3 }}
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </motion.svg>
          </button>
          
          {expandedSections.trials && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="px-8 pb-8"
            >
              <div className="space-y-3">
                {clinical_trials.slice(0, 8).map((trial, index) => (
                  <motion.div
                    key={trial.nct_id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.4 + index * 0.05 }}
                    whileHover={{ scale: 1.01, x: 4 }}
                    className="backdrop-blur-sm bg-white/50 p-5 rounded-2xl border border-apple-gray-200/30 hover:bg-white/70 hover:shadow-apple transition-all duration-300 group"
                  >
                    <div className="flex items-start justify-between gap-4 mb-3">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          {/* Provenance Icon */}
                          <svg className="w-4 h-4 text-apple-lavender-500" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M6 6V5a3 3 0 013-3h2a3 3 0 013 3v1h2a2 2 0 012 2v3.57A22.952 22.952 0 0110 13a22.95 22.95 0 01-8-1.43V8a2 2 0 012-2h2zm2-1a1 1 0 011-1h2a1 1 0 011 1v1H8V5zm1 5a1 1 0 011-1h.01a1 1 0 110 2H10a1 1 0 01-1-1z" clipRule="evenodd" />
                            <path d="M2 13.692V16a2 2 0 002 2h12a2 2 0 002-2v-2.308A24.974 24.974 0 0110 15c-2.796 0-5.487-.46-8-1.308z" />
                          </svg>
                          <span className="text-xs text-apple-gray-500 font-medium">ClinicalTrials.gov</span>
                        </div>
                        <h4 className="font-semibold text-apple-gray-800 group-hover:text-apple-lavender-600 transition-colors line-clamp-2">
                          {trial.title}
                        </h4>
                        <p className="text-xs text-apple-gray-500 mt-1">{trial.nct_id}</p>
                      </div>
                      {trial.match_score > 0 && (
                        <span className={`text-sm ${getMatchScoreStyle(trial.match_score)} whitespace-nowrap`}>
                          {Math.round(trial.match_score * 100)}%
                        </span>
                      )}
                    </div>
                    
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`px-3 py-1 rounded-full text-xs font-medium ${getPhaseStyle(trial.phase)}`}>
                        {trial.phase}
                      </span>
                      <span className="px-3 py-1 rounded-full text-xs font-medium bg-apple-gray-100/60 text-apple-gray-700">
                        {trial.status}
                      </span>
                      {trial.location && (
                        <span className="text-xs text-apple-gray-600 flex items-center gap-1">
                          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                          </svg>
                          {trial.location}
                        </span>
                      )}
                    </div>
                  </motion.div>
                ))}
              </div>
            </motion.div>
          )}
        </motion.div>
      )}

      {/* Patents - Card Grid */}
      {patents.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4, duration: 0.5 }}
          className="backdrop-blur-glass bg-white/70 rounded-3xl shadow-apple border border-white/30 overflow-hidden"
        >
          <button
            onClick={() => toggleSection('patents')}
            className="w-full px-8 py-6 flex items-center justify-between hover:bg-white/50 transition-colors"
          >
            <div className="flex items-center gap-3">
              <span className="text-2xl">📄</span>
              <h3 className="text-xl font-semibold text-apple-gray-800">
                Patents
                <span className="ml-2 text-apple-gray-500 font-normal text-base">({patents.length})</span>
              </h3>
            </div>
            <motion.svg
              className="w-6 h-6 text-apple-gray-500"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              animate={{ rotate: expandedSections.patents ? 180 : 0 }}
              transition={{ duration: 0.3 }}
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </motion.svg>
          </button>
          
          {expandedSections.patents && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="px-8 pb-8"
            >
              {/* Legal Disclaimer */}
              <div className="bg-apple-amber-50/50 border border-apple-amber-200/40 p-4 mb-6 rounded-2xl backdrop-blur-sm">
                <div className="flex gap-3">
                  <span className="text-xl flex-shrink-0">⚠️</span>
                  <div>
                    <h4 className="text-sm font-semibold text-apple-amber-700 mb-1">
                      Legal Disclaimer - Freedom to Operate (FTO)
                    </h4>
                    <p className="text-xs text-apple-amber-700/90 leading-relaxed mb-1.5">
                      <strong>Important:</strong> Patent information is for research purposes only and does not constitute legal advice. 
                      This is not a comprehensive FTO analysis. Consult qualified patent attorneys before commercialization.
                    </p>
                    <p className="text-xs text-apple-amber-700/80 leading-relaxed">
                      <strong>Data Source:</strong> Curated from publicly available USPTO records. For production, integrate with authenticated APIs.
                    </p>
                  </div>
                </div>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {patents.slice(0, 8).map((patent, index) => (
                  <motion.a
                    key={patent.patent_id}
                    href={patent.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 0.5 + index * 0.05 }}
                    whileHover={{ scale: 1.02, y: -2 }}
                    className="backdrop-blur-sm bg-white/50 p-5 rounded-2xl border border-apple-gray-200/30 hover:bg-white/70 hover:shadow-apple transition-all duration-300 group block"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <p className="font-mono text-sm font-semibold text-apple-lavender-600 group-hover:text-apple-lavender-700">
                        {patent.patent_id}
                      </p>
                      <svg className="w-4 h-4 text-apple-gray-400 group-hover:text-apple-lavender-500 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                      </svg>
                    </div>
                    
                    <h4 className="text-sm font-medium text-apple-gray-800 mb-3 line-clamp-2 leading-snug">
                      {patent.title}
                    </h4>
                    
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-apple-gray-600 truncate">{patent.assignee}</span>
                      <span className="px-2.5 py-1 bg-apple-mint-100/60 text-apple-mint-700 rounded-full font-medium ml-2 flex-shrink-0">
                        {patent.status}
                      </span>
                    </div>
                    
                    <p className="text-xs text-apple-gray-500 mt-2">{patent.filing_date}</p>
                  </motion.a>
                ))}
              </div>
            </motion.div>
          )}
        </motion.div>
      )}

      {/* Web Intelligence */}
      {web_intel.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5, duration: 0.5 }}
          className="backdrop-blur-glass bg-white/70 rounded-3xl shadow-apple border border-white/30 overflow-hidden"
        >
          <button
            onClick={() => toggleSection('literature')}
            className="w-full px-8 py-6 flex items-center justify-between hover:bg-white/50 transition-colors"
          >
            <div className="flex items-center gap-3">
              <span className="text-2xl">🌐</span>
              <h3 className="text-xl font-semibold text-apple-gray-800">
                Scientific Literature
                <span className="ml-2 text-apple-gray-500 font-normal text-base">({web_intel.length})</span>
              </h3>
            </div>
            <motion.svg
              className="w-6 h-6 text-apple-gray-500"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              animate={{ rotate: expandedSections.literature ? 180 : 0 }}
              transition={{ duration: 0.3 }}
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </motion.svg>
          </button>
          
          {expandedSections.literature && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="px-8 pb-8"
            >
              <div className="space-y-3">
                {web_intel.slice(0, 8).map((intel, index) => (
                  <motion.a
                    key={index}
                    href={intel.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.6 + index * 0.05 }}
                    whileHover={{ scale: 1.01, x: 4 }}
                    className="backdrop-blur-sm bg-white/50 p-5 rounded-2xl border border-apple-gray-200/30 hover:bg-white/70 hover:shadow-apple transition-all duration-300 group block focus:outline-none focus:ring-2 focus:ring-apple-lavender-400 focus:ring-offset-2"
                  >
                    <div className="flex items-start justify-between gap-4 mb-2">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          {/* Provenance Icon */}
                          <svg className="w-4 h-4 text-apple-lavender-500" fill="currentColor" viewBox="0 0 20 20">
                            <path d="M9 4.804A7.968 7.968 0 005.5 4c-1.255 0-2.443.29-3.5.804v10A7.969 7.969 0 015.5 14c1.669 0 3.218.51 4.5 1.385A7.962 7.962 0 0114.5 14c1.255 0 2.443.29 3.5.804v-10A7.968 7.968 0 0014.5 4c-1.255 0-2.443.29-3.5.804V12a1 1 0 11-2 0V4.804z" />
                          </svg>
                          <span className="text-xs text-apple-gray-500 font-medium">{intel.source}</span>
                        </div>
                        <h4 className="font-semibold text-apple-gray-800 group-hover:text-apple-lavender-600 transition-colors leading-snug">
                          {intel.title}
                        </h4>
                      </div>
                      {intel.relevance_score > 0 && (
                        <span className={`text-sm ${getMatchScoreStyle(intel.relevance_score)} whitespace-nowrap`}>
                          {Math.round(intel.relevance_score * 100)}%
                        </span>
                      )}
                    </div>
                    
                    <p className="text-sm text-apple-gray-600 mb-3 line-clamp-2 leading-relaxed">
                      {intel.snippet}
                    </p>
                    
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-apple-gray-500 flex items-center gap-1">
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                        </svg>
                        View source
                      </span>
                      <svg className="w-4 h-4 text-apple-gray-400 group-hover:text-apple-lavender-500 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                      </svg>
                    </div>
                  </motion.a>
                ))}
              </div>
            </motion.div>
          )}
        </motion.div>
      )}
    </div>
  )
}
