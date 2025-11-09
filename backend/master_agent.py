"""
Master Agent - Orchestrates worker agents and synthesizes results
"""
import os
import json
import asyncio
from typing import Dict, Any, List
from datetime import datetime
from google import genai

from agents.clinical_trials_agent import ClinicalTrialsAgent
from agents.patent_agent import PatentAgent
from agents.web_intel_agent import WebIntelAgent
from agents.web_search_agent import WebSearchAgent
from job_manager import JobManager
from sse_manager import sse_manager
from models import JobStatus, AgentStatus
from report_generator import ReportGenerator
from query_normalizer import QueryNormalizer
from semantic_search import SemanticSearchEngine  # Now using Gemini API


class MasterAgent:
    """Master orchestrator for multi-agent pharmaceutical analysis"""
    
    def __init__(self):
        self.name = "Master Agent"
        self.job_manager = JobManager()
        self.report_generator = ReportGenerator()
        self.query_normalizer = QueryNormalizer()
        self.semantic_search = SemanticSearchEngine()  # Using Gemini API (lightweight)
        # Configurable max results per agent (default 20)
        try:
            self.max_results = int(os.getenv("MAX_RESULTS_PER_AGENT", "20"))
        except Exception:
            self.max_results = 20
        
        # Initialize worker agents
        self.clinical_trials_agent = ClinicalTrialsAgent()
        self.patent_agent = PatentAgent()
        self.web_intel_agent = WebIntelAgent()
        self.web_search_agent = WebSearchAgent()
    
    async def process_query(self, job_id: str, query: str):
        """
        Main orchestration logic:
        1. Normalize query with MeSH mapping
        2. Parse intent and plan tasks
        3. Delegate to worker agents with expanded terms
        4. Synthesize and re-rank results
        5. Generate PDF report
        """
        try:
            print(f"🎯 {self.name}: Starting analysis for job {job_id}")
            
            # Update job status
            self.job_manager.update_job(job_id, {"status": JobStatus.RUNNING.value})
            await self._send_ws_update(job_id, "job_started", {"query": query})
            
            # Step 1: Normalize query with MeSH mapping and synonym expansion
            await self._update_master_status(job_id, AgentStatus.RUNNING)
            normalized = self.query_normalizer.normalize_query(query)
            print(f"📋 Normalized query: {normalized['normalized']}")
            print(f"📋 Canonical terms: {normalized['canonical_terms']}")
            
            # Parse intent with normalized query
            intent = self._parse_intent(query)
            intent["normalized"] = normalized  # Add normalized data to intent
            await asyncio.sleep(0.5)
            await self._update_master_status(job_id, AgentStatus.COMPLETED)
            self.job_manager.update_job(job_id, {"progress": 10})
            
            # Optional: AI-assisted term expansion for broader coverage
            normalized = await self._expand_search_terms_with_ai(query, normalized)

            # Step 2: Run worker agents in parallel with normalized/expanded queries
            await self._send_ws_update(job_id, "progress_update", {
                "message": "Starting parallel agent execution...",
                "progress": 15
            })
            results = await self._run_workers(job_id, query, intent)
            self.job_manager.update_job(job_id, {"progress": 70})
            await self._send_ws_update(job_id, "progress_update", {
                "message": "All agents completed, synthesizing results...",
                "progress": 70
            })
            
            # Step 3: Synthesize findings with match scoring
            await self._update_master_status(job_id, AgentStatus.RUNNING)
            analysis = self._synthesize_results(query, results, intent)
            await asyncio.sleep(1)
            self.job_manager.update_job(job_id, {"progress": 85})
            await self._send_ws_update(job_id, "progress_update", {
                "message": "Generating comprehensive report...",
                "progress": 85
            })
            
            # Step 4: Generate report (PDF or text fallback)
            report_path = await self.report_generator.generate(job_id, query, analysis)
            
            # Determine file extension from report_path
            import os
            file_name = os.path.basename(report_path)
            analysis["report_url"] = f"/api/reports/{file_name}"
            self.job_manager.update_job(job_id, {"progress": 95})
            
            # Step 5: Save final results
            final_result = {
                "job_id": job_id,
                "query": query,
                "status": JobStatus.COMPLETED.value,
                **analysis,
                "created_at": self.job_manager.get_job(job_id)["created_at"],
                "completed_at": datetime.utcnow().isoformat()
            }
            
            self.job_manager.save_result(job_id, final_result)
            self.job_manager.update_job(job_id, {
                "status": JobStatus.COMPLETED.value,
                "progress": 100
            })
            await self._update_master_status(job_id, AgentStatus.COMPLETED)
            
            # Notify completion via WebSocket
            await self._send_ws_update(job_id, "job_completed", {
                "job_id": job_id,
                "report_url": analysis["report_url"],
                "status": "completed"
            })
            
            print(f"✅ {self.name}: Analysis completed for job {job_id}")
            
        except Exception as e:
            print(f"❌ {self.name}: Error processing job {job_id}: {e}")
            self.job_manager.update_job(job_id, {"status": JobStatus.FAILED.value})
            await self._send_ws_update(job_id, "job_failed", {"error": str(e)})
    
    def _parse_intent(self, query: str) -> Dict[str, Any]:
        """Parse user query to understand intent and extract parameters"""
        query_lower = query.lower()
        
        intent = {
            "focus_areas": [],
            "geographic_region": None,
            "analysis_type": "competitive_landscape"
        }
        
        # Detect focus areas
        if any(word in query_lower for word in ["competition", "competitive", "market"]):
            intent["focus_areas"].append("competition_analysis")
        if any(word in query_lower for word in ["burden", "prevalence", "patients"]):
            intent["focus_areas"].append("patient_burden")
        if any(word in query_lower for word in ["opportunity", "gap", "unmet"]):
            intent["focus_areas"].append("opportunity_detection")
        
        # Detect geography
        regions = {
            "india": "India",
            "china": "China",
            "united states": "United States",
            "europe": "Europe",
            "asia": "Asia"
        }
        for key, value in regions.items():
            if key in query_lower:
                intent["geographic_region"] = value
                break
        
        return intent
    
    async def _run_workers(self, job_id: str, query: str, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Run all worker agents in parallel with timeouts, expanded terms, and graceful failures"""
        
        # Extract normalized/expanded terms from intent
        normalized = intent.get("normalized", {})
        search_terms = normalized.get("search_terms", {})
        
        # Clinical Trials Agent with timeout and expanded terms
        async def run_clinical():
            try:
                self.job_manager.update_agent_status(
                    job_id, "Clinical Trials Agent", AgentStatus.RUNNING
                )
                await self._send_ws_update(job_id, "agent_update", {
                    "agent": "Clinical Trials Agent",
                    "status": "running"
                })
                
                # Pass expanded terms for better search
                expanded = search_terms.get("clinical_trials", [])
                
                # 30-second timeout for clinical trials search
                results = await asyncio.wait_for(
                    self.clinical_trials_agent.search(query, max_results=self.max_results, expanded_terms=expanded), 
                    timeout=30.0
                )
                competition = await self.clinical_trials_agent.analyze_competition(results)
                
                self.job_manager.update_agent_status(
                    job_id, "Clinical Trials Agent", AgentStatus.COMPLETED, len(results)
                )
                await self._send_ws_update(job_id, "agent_update", {
                    "agent": "Clinical Trials Agent",
                    "status": "completed",
                    "result_count": len(results)
                })
                
                return {"trials": results, "competition_analysis": competition}
            except asyncio.TimeoutError:
                print(f"⚠️ Clinical Trials Agent: Timeout after 30s")
                self.job_manager.update_agent_status(
                    job_id, "Clinical Trials Agent", AgentStatus.FAILED, 0, "Timeout"
                )
                await self._send_ws_update(job_id, "agent_update", {
                    "agent": "Clinical Trials Agent",
                    "status": "failed",
                    "error": "Timeout"
                })
                return {"trials": [], "competition_analysis": {}}
            except Exception as e:
                self.job_manager.update_agent_status(
                    job_id, "Clinical Trials Agent", AgentStatus.FAILED, error=str(e)
                )
                return {"trials": [], "competition_analysis": {}}
        
        # Patent Agent with timeout and expanded terms
        async def run_patent():
            try:
                self.job_manager.update_agent_status(
                    job_id, "Patent Agent", AgentStatus.RUNNING
                )
                await self._send_ws_update(job_id, "agent_update", {
                    "agent": "Patent Agent",
                    "status": "running"
                })
                
                # Pass expanded terms (focused for patents)
                expanded = search_terms.get("patents", [])
                
                # 30-second timeout for patent search
                results = await asyncio.wait_for(
                    self.patent_agent.search(query, max_results=self.max_results, expanded_terms=expanded),
                    timeout=30.0
                )
                
                self.job_manager.update_agent_status(
                    job_id, "Patent Agent", AgentStatus.COMPLETED, len(results)
                )
                await self._send_ws_update(job_id, "agent_update", {
                    "agent": "Patent Agent",
                    "status": "completed",
                    "result_count": len(results)
                })
                
                return results
            except asyncio.TimeoutError:
                print(f"⚠️ Patent Agent: Timeout after 30s")
                self.job_manager.update_agent_status(
                    job_id, "Patent Agent", AgentStatus.FAILED, 0, "Timeout"
                )
                await self._send_ws_update(job_id, "agent_update", {
                    "agent": "Patent Agent",
                    "status": "failed",
                    "error": "Timeout"
                })
                return []
            except Exception as e:
                self.job_manager.update_agent_status(
                    job_id, "Patent Agent", AgentStatus.FAILED, error=str(e)
                )
                return []
        
        # Web Intel Agent with timeout and expanded terms
        async def run_web():
            try:
                self.job_manager.update_agent_status(
                    job_id, "Web Intel Agent", AgentStatus.RUNNING
                )
                await self._send_ws_update(job_id, "agent_update", {
                    "agent": "Web Intel Agent",
                    "status": "running"
                })
                
                # Pass expanded terms (broader for literature)
                expanded = search_terms.get("literature", [])
                
                # 30-second timeout for web intel search
                results = await asyncio.wait_for(
                    self.web_intel_agent.search(query, max_results=self.max_results, expanded_terms=expanded),
                    timeout=30.0
                )
                
                self.job_manager.update_agent_status(
                    job_id, "Web Intel Agent", AgentStatus.COMPLETED, len(results)
                )
                await self._send_ws_update(job_id, "agent_update", {
                    "agent": "Web Intel Agent",
                    "status": "completed",
                    "result_count": len(results)
                })
                
                return results
            except asyncio.TimeoutError:
                print(f"⚠️ Web Intel Agent: Timeout after 30s")
                self.job_manager.update_agent_status(
                    job_id, "Web Intel Agent", AgentStatus.FAILED, 0, "Timeout"
                )
                await self._send_ws_update(job_id, "agent_update", {
                    "agent": "Web Intel Agent",
                    "status": "failed",
                    "error": "Timeout"
                })
                return []
            except Exception as e:
                self.job_manager.update_agent_status(
                    job_id, "Web Intel Agent", AgentStatus.FAILED, error=str(e)
                )
                return []

        # Web Search Agent (DuckDuckGo + Wikipedia) for general context
        async def run_web_search():
            try:
                self.job_manager.update_agent_status(
                    job_id, "Web Search Agent", AgentStatus.RUNNING
                )
                await self._send_ws_update(job_id, "agent_update", {
                    "agent": "Web Search Agent",
                    "status": "running"
                })
                results = await asyncio.wait_for(
                    self.web_search_agent.search(query, max_results=min(10, self.max_results)),
                    timeout=20.0
                )
                self.job_manager.update_agent_status(
                    job_id, "Web Search Agent", AgentStatus.COMPLETED, len(results)
                )
                await self._send_ws_update(job_id, "agent_update", {
                    "agent": "Web Search Agent",
                    "status": "completed",
                    "result_count": len(results)
                })
                return results
            except asyncio.TimeoutError:
                self.job_manager.update_agent_status(
                    job_id, "Web Search Agent", AgentStatus.FAILED, 0, "Timeout"
                )
                await self._send_ws_update(job_id, "agent_update", {
                    "agent": "Web Search Agent", "status": "failed", "error": "Timeout"
                })
                return []
            except Exception as e:
                self.job_manager.update_agent_status(
                    job_id, "Web Search Agent", AgentStatus.FAILED, error=str(e)
                )
                return []
        
        # Run all workers in parallel (continue even if some fail)
        clinical_data, patents, web_intel, web_search = await asyncio.gather(
            run_clinical(),
            run_patent(),
            run_web(),
            run_web_search(),
            return_exceptions=False  # Already handled exceptions in each function
        )
        
        return {
            "clinical_trials": clinical_data["trials"],
            "competition_analysis": clinical_data["competition_analysis"],
            "patents": patents,
            "web_intel": web_intel + web_search
        }
    
    def _synthesize_results(self, query: str, results: Dict[str, Any], intent: Dict[str, Any]) -> Dict[str, Any]:
        """
        Synthesize findings from all agents with semantic re-ranking (Phase 4)
        """
        
        clinical_trials = results["clinical_trials"]
        competition = results["competition_analysis"]
        patents = results["patents"]
        web_intel = results["web_intel"]
        
        print(f"🧠 Applying AI-powered semantic re-ranking...")
        
        # Phase 4: Semantic re-ranking using Gemini API
        clinical_trials_ranked = self.semantic_search.re_rank_clinical_trials(query, clinical_trials)
        patents_ranked = self.semantic_search.re_rank_patents(query, patents)
        web_intel_ranked = self.semantic_search.re_rank_literature(query, web_intel)
        
        # Phase 4: Compute confidence score with AI
        confidence_score, confidence_level = self.semantic_search.compute_confidence_score(
            query, clinical_trials_ranked, patents_ranked, web_intel_ranked
        )
        
        # Generate executive summary
        exec_summary = self._generate_executive_summary(
            query, clinical_trials_ranked, competition, patents_ranked, web_intel_ranked, intent
        )
        
        # Generate key findings
        key_findings = self._generate_key_findings(
            clinical_trials_ranked, competition, patents_ranked, web_intel_ranked, intent
        )
        
        # Add confidence finding
        key_findings.insert(0, 
            f"Analysis Confidence: {confidence_level} ({confidence_score:.0f}/100) - "
            f"Based on {len(clinical_trials_ranked)} trials, {len(patents_ranked)} patents, "
            f"{len(web_intel_ranked)} publications"
        )
        
        return {
            "executive_summary": exec_summary,
            "key_findings": key_findings,
            "clinical_trials": [trial.dict() for trial in clinical_trials_ranked[:15]],  # Top 15
            "patents": [patent.dict() for patent in patents_ranked[:15]],  # Top 15
            "web_intel": [intel.dict() for intel in web_intel_ranked[:15]],  # Top 15
            "confidence_score": confidence_score,
            "confidence_level": confidence_level
        }
    
    def _generate_executive_summary(self, query: str, trials, competition, 
                                   patents, web_intel, intent) -> str:
        """Generate AI-driven executive summary using Gemini"""
        
        # Try to use Gemini for enhanced summary
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if api_key:
            try:
                client = genai.Client(api_key=api_key)
                model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")
                
                # Prepare concise data for Gemini
                region = intent.get("geographic_region", "the targeted region")
                competition_level = competition.get("competition_level", "moderate")
                active_trials = competition.get("active_trials", 0)
                total_trials = competition.get("total_trials", 0)
                focus_areas = intent.get("focus_areas", [])
                
                # Get top trial titles
                trial_titles = [getattr(t, 'title', 'N/A')[:100] for t in trials[:5]]
                patent_titles = [getattr(p, 'title', 'N/A')[:100] for p in patents[:3]]
                
                prompt = f"""You are a pharmaceutical research analyst. Create a compelling executive summary (3-4 sentences, professional tone).

Query: "{query}"

Key Data:
- {total_trials} clinical trials found ({active_trials} active/recruiting)
- Competition level: {competition_level} in {region}
- {len(patents)} relevant patents
- {len(web_intel)} scientific publications
- Focus areas: {', '.join(focus_areas)}

Top Trials: {trial_titles[:3]}
Top Patents: {patent_titles[:2]}

Write a concise, insightful executive summary highlighting opportunities, competition, and market potential."""

                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                summary = (getattr(response, 'text', '') or '').strip()
                
                print(f"✅ Generated AI-powered executive summary")
                return summary
                
            except Exception as e:
                print(f"⚠️ Gemini summary failed: {e}, using template")
        
        # Fallback to template-based summary
        region = intent.get("geographic_region", "the targeted region")
        competition_level = competition.get("competition_level", "moderate")
        active_trials = competition.get("active_trials", 0)
        total_trials = competition.get("total_trials", 0)
        
        summary = f"Analysis of '{query}' reveals {total_trials} relevant clinical trials, "
        summary += f"with {active_trials} currently active or recruiting. "
        summary += f"The competitive landscape shows {competition_level} competition "
        summary += f"in {region}. "
        
        if competition_level == "low" and active_trials < 5:
            summary += "This represents a significant opportunity for market entry with limited direct competition. "
        
        summary += f"Patent analysis identified {len(patents)} relevant patents, "
        summary += f"and web intelligence gathered {len(web_intel)} supporting data points. "
        
        if "patient_burden" in intent["focus_areas"]:
            summary += "Patient burden indicators suggest substantial unmet medical need in this therapeutic area."
        
        return summary
    
    def _generate_key_findings(self, trials, competition, patents, web_intel, intent) -> List[str]:
        """Generate key findings list"""
        findings = []
        
        # Competition finding
        comp_level = competition.get("competition_level", "unknown")
        findings.append(
            f"Competitive Analysis: {comp_level.title()} competition detected with "
            f"{competition.get('active_trials', 0)} active trials"
        )
        
        # Phase distribution
        phase_dist = competition.get("phase_distribution", {})
        if phase_dist:
            findings.append(
                f"Trial Phases: Most activity in {max(phase_dist, key=phase_dist.get) if phase_dist else 'Phase 2/3'}"
            )
        
        # Patent landscape
        if patents:
            active_patents = sum(1 for p in patents if p.status == "Active")
            findings.append(
                f"Patent Landscape: {len(patents)} relevant patents identified, "
                f"{active_patents} currently active"
            )
        
        # Market opportunity
        if comp_level == "low":
            findings.append(
                "Market Opportunity: Low competition suggests favorable conditions for new entrants"
            )
        
        # Geographic insights
        if intent.get("geographic_region"):
            findings.append(
                f"Geographic Focus: Analysis concentrated on {intent['geographic_region']} market dynamics"
            )
        
        return findings
    
    async def _update_master_status(self, job_id: str, status: AgentStatus):
        """Update master agent status"""
        self.job_manager.update_agent_status(job_id, "Master Agent", status)
    
    async def _send_ws_update(self, job_id: str, event_type: str, data: Dict[str, Any]):
        """Send SSE update"""
        await sse_manager.send_update(job_id, event_type, data)

    async def _expand_search_terms_with_ai(self, query: str, normalized: Dict[str, Any]) -> Dict[str, Any]:
        """Use Gemini to expand canonical terms and synonyms for better recall.
        Returns an updated normalized dict with enriched search_terms.
        """
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return normalized
        try:
            client = genai.Client(api_key=api_key)
            model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")
            base_terms = normalized.get("search_terms", {})
            prompt = f"""
You are a medical research assistant. Expand search terms for a clinical research platform.
Query: "{query}"

Given existing terms:
{json.dumps(base_terms, indent=2)}

Return ONLY a compact JSON object with keys exactly: clinical_trials, patents, literature.
Each key maps to an array of 5-10 short strings (disease names, drug classes, related concepts).
No explanation, no markdown, just JSON.
"""
            response = client.models.generate_content(model=model_name, contents=prompt)
            txt = (getattr(response, 'text', '') or '').strip()
            # Extract JSON object
            s = txt
            if s.startswith("```"):
                s = s.strip('`\n ')
                if "\n" in s:
                    s = s.split("\n", 1)[1]
            try:
                expanded = json.loads(s)
                # Merge with existing search_terms conservatively
                merged = {
                    "clinical_trials": list({*(base_terms.get("clinical_trials", [])), *expanded.get("clinical_trials", [])})[:10],
                    "patents": list({*(base_terms.get("patents", [])), *expanded.get("patents", [])})[:8],
                    "literature": list({*(base_terms.get("literature", [])), *expanded.get("literature", [])})[:12],
                }
                normalized["search_terms"] = merged
            except Exception:
                # Ignore parsing errors; keep original terms
                pass
        except Exception:
            # If AI call fails, keep original normalized terms
            pass
        return normalized
