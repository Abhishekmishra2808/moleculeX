"""
Clinical Trials Worker Agent
Fetches live data from multiple clinical trial registries for comprehensive coverage
Uses working, keyless APIs with proper error handling
"""
import httpx
import asyncio
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
from datetime import datetime
from models import ClinicalTrialResult


class ClinicalTrialsAgent:
    """Agent for fetching clinical trial data from multiple working sources"""
    
    # Primary working endpoints (tested and verified)
    EUROPE_PMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    PUBMED_SEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    PUBMED_SUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    PUBMED_FETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    CROSSREF_API = "https://api.crossref.org/works"
    
    # ClinicalTrials.gov (may face 403 errors - fallback available)
    CLINICALTRIALS_GOV = "https://clinicaltrials.gov/api/v2/studies"
    CTGOV_LEGACY = "https://clinicaltrials.gov/api/query/study_fields"
    
    def __init__(self):
        self.name = "Clinical Trials Agent"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }
    
    async def search(self, query: str, max_results: int = 20, expanded_terms: List[str] = None) -> List[ClinicalTrialResult]:
        """
        Search multiple clinical trial registries for comprehensive coverage
        
        Args:
            query: Search query (disease, drug, condition, etc.)
            max_results: Maximum number of results to return (default 20)
            expanded_terms: Canonicalized/expanded medical terms from query normalizer
            
        Returns:
            List of structured clinical trial results from multiple sources
        """
        print(f"🔬 {self.name}: Starting multi-source search for '{query}'")
        if expanded_terms:
            print(f"📋 Using expanded terms: {expanded_terms[:5]}")
        
        search_terms = self._extract_keywords(query)
        
        # Fetch from all working sources in parallel
        tasks = [
            self._search_europe_pmc(query, search_terms, expanded_terms, max_results // 3),
            self._search_pubmed_clinical_trials(query, search_terms, expanded_terms, max_results // 3),
            self._search_crossref(query, search_terms, expanded_terms, max_results // 4),
            self._search_clinicaltrials_gov_safe(query, search_terms, expanded_terms, max_results // 3),
        ]
        
        results_lists = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Combine, normalize, and deduplicate
        normalized_results: List[ClinicalTrialResult] = []
        seen_ids = set()

        for results in results_lists:
            if isinstance(results, list):
                for trial in results:
                    if isinstance(trial, ClinicalTrialResult):
                        obj = trial
                    elif isinstance(trial, dict):
                        try:
                            obj = ClinicalTrialResult(
                                nct_id=trial.get("nct_id", "N/A") or "N/A",
                                title=trial.get("title", "Untitled Study"),
                                status=trial.get("status", "Unknown"),
                                phase=trial.get("phase"),
                                condition=trial.get("condition", ""),
                                intervention=trial.get("intervention"),
                                sponsor=trial.get("sponsor"),
                                start_date=trial.get("start_date"),
                                completion_date=trial.get("completion_date"),
                                enrollment=trial.get("enrollment"),
                                location=trial.get("location"),
                                source_url=trial.get("source_url", ""),
                                retrieved_at=trial.get("retrieved_at", "") or "",
                                match_score=float(trial.get("match_score", 0.0) or 0.0),
                                matched_terms=trial.get("matched_terms", []),
                            )
                        except Exception:
                            continue
                    else:
                        continue

                    trial_id = obj.nct_id or obj.title
                    if trial_id and trial_id not in seen_ids:
                        seen_ids.add(trial_id)
                        normalized_results.append(obj)

        print(f"✅ {self.name}: Found {len(normalized_results)} unique trials from all sources")
        return normalized_results[:max_results]
    
    async def _search_europe_pmc(self, query: str, search_terms: dict, expanded_terms: List[str], max_results: int) -> List[Dict[str, Any]]:
        """Search Europe PMC for clinical trial publications (PRIMARY SOURCE)"""
        try:
            # Build search query with clinical trial filter
            if expanded_terms and len(expanded_terms) > 0:
                search_query = " OR ".join(expanded_terms[:3])
            else:
                search_query = search_terms.get("condition", query)
            
            # Add clinical trial filter
            full_query = f"({search_query}) AND (METHODS:\"clinical trial\" OR METHODS:\"randomized controlled trial\")"
            
            params = {
                "query": full_query,
                "format": "json",
                "pageSize": max_results,
                "synonym": "true",  # Enable MeSH synonym expansion
                "resultType": "core"
            }
            
            print(f"🌐 Querying Europe PMC...")
            
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(self.EUROPE_PMC, params=params, headers=self.headers)
                response.raise_for_status()
                data = response.json()
                
                results = []
                articles = data.get("resultList", {}).get("result", [])
                
                for article in articles:
                    try:
                        pmid = article.get("pmid", "")
                        pmcid = article.get("pmcid", "")
                        doi = article.get("doi", "")
                        
                        # Generate unique ID
                        nct_id = pmcid or f"PMID{pmid}" or f"DOI{doi}" or "EuropePMC"
                        
                        results.append({
                            "nct_id": nct_id,
                            "title": article.get("title", "Untitled Study"),
                            "status": "PUBLISHED",
                            "phase": None,
                            "condition": search_query[:100],
                            "intervention": None,
                            "sponsor": article.get("authorString", "")[:50] if article.get("authorString") else None,
                            "start_date": article.get("firstPublicationDate"),
                            "completion_date": None,
                            "enrollment": None,
                            "location": article.get("affiliation", "")[:50] if article.get("affiliation") else None,
                            "source_url": f"https://europepmc.org/article/MED/{pmid}" if pmid else f"https://europepmc.org/article/PMC/{pmcid}",
                            "retrieved_at": datetime.now().isoformat(),
                            "match_score": 0.9,
                            "matched_terms": expanded_terms[:3] if expanded_terms else [query]
                        })
                    except Exception:
                        continue
                
                print(f"✅ Europe PMC: {len(results)} clinical trial publications")
                return results
                
        except Exception as e:
            print(f"⚠️ Europe PMC error: {e}")
            return []
    
    async def _search_crossref(self, query: str, search_terms: dict, expanded_terms: List[str], max_results: int) -> List[Dict[str, Any]]:
        """Search Crossref for clinical trial publications"""
        try:
            if expanded_terms and len(expanded_terms) > 0:
                search_query = " ".join(expanded_terms[:3])
            else:
                search_query = search_terms.get("condition", query)
            
            params = {
                "query": f"{search_query} clinical trial",
                "rows": max_results,
                "filter": "has-clinical-trial-number:true,type:journal-article"
            }
            
            print(f"🌐 Querying Crossref API...")
            
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(self.CROSSREF_API, params=params, headers=self.headers)
                response.raise_for_status()
                data = response.json()
                
                results = []
                items = data.get("message", {}).get("items", [])
                
                for item in items:
                    try:
                        doi = item.get("DOI", "")
                        title = item.get("title", ["Untitled"])[0] if item.get("title") else "Untitled"
                        
                        # Extract clinical trial numbers
                        clinical_trial_nums = item.get("clinical-trial-number", [])
                        nct_id = clinical_trial_nums[0].get("clinical-trial-number") if clinical_trial_nums else f"DOI{doi}"
                        
                        # Extract authors
                        authors = item.get("author", [])
                        author_str = ", ".join([f"{a.get('given', '')} {a.get('family', '')}".strip() for a in authors[:2]])
                        
                        # Extract publication date
                        pub_date = item.get("published", {}).get("date-parts", [[]])[0]
                        pub_date_str = "-".join(map(str, pub_date)) if pub_date else None
                        
                        results.append({
                            "nct_id": nct_id,
                            "title": title,
                            "status": "PUBLISHED",
                            "phase": None,
                            "condition": search_query[:100],
                            "intervention": None,
                            "sponsor": item.get("publisher", author_str)[:100],
                            "start_date": pub_date_str,
                            "completion_date": None,
                            "enrollment": None,
                            "location": None,
                            "source_url": f"https://doi.org/{doi}" if doi else "",
                            "retrieved_at": datetime.now().isoformat(),
                            "match_score": 0.85,
                            "matched_terms": expanded_terms[:3] if expanded_terms else [query]
                        })
                    except Exception:
                        continue
                
                print(f"✅ Crossref: {len(results)} clinical trial publications")
                return results
                
        except Exception as e:
            print(f"⚠️ Crossref error: {e}")
            return []
    
    async def _search_clinicaltrials_gov_safe(self, query: str, search_terms: dict, expanded_terms: List[str], max_results: int) -> List[Dict[str, Any]]:
        """
        Safe wrapper for ClinicalTrials.gov with automatic fallback
        Handles 403 errors gracefully and falls back to legacy API
        """
        try:
            # Try v2 API first with rate limiting
            await asyncio.sleep(2)  # Rate limit protection
            return await self._search_clinicaltrials_gov(query, search_terms, expanded_terms, max_results)
        except Exception as e:
            if "403" in str(e) or "Forbidden" in str(e):
                print(f"⚠️ ClinicalTrials.gov v2 blocked, trying legacy API...")
                try:
                    await asyncio.sleep(2)  # Rate limit protection
                    return await self._search_ctgov_legacy(query, search_terms, expanded_terms, max_results)
                except Exception as e2:
                    print(f"⚠️ ClinicalTrials.gov legacy also failed: {e2}")
                    return []
            else:
                print(f"⚠️ ClinicalTrials.gov error: {e}")
                return []
    
    async def _search_clinicaltrials_gov(self, query: str, search_terms: dict, expanded_terms: List[str], max_results: int) -> List[Dict[str, Any]]:
        """Search ClinicalTrials.gov v2 API"""
        if expanded_terms and len(expanded_terms) > 0:
            search_query = " OR ".join(expanded_terms[:5])
        else:
            search_query = search_terms.get("condition", query)
        
        params = {
            "query.cond": search_query,
            "pageSize": max_results,
            "countTotal": "true",
            "format": "json"
        }
        
        if search_terms.get("location"):
            params["query.locn"] = search_terms["location"]
        
        print(f"🌐 Querying ClinicalTrials.gov v2...")
        
        async with httpx.AsyncClient(timeout=20.0) as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
                "Referer": "https://clinicaltrials.gov/",
            }
            response = await client.get(self.CLINICALTRIALS_GOV, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            studies = data.get("studies", [])
            results = []
            for study in studies:
                try:
                    result = self._parse_study(study)
                    results.append(result.__dict__)
                except Exception:
                    continue
            
            print(f"✅ ClinicalTrials.gov v2: {len(results)} trials")
            return results

    async def _search_ctgov_legacy(self, query: str, search_terms: dict, expanded_terms: List[str], max_results: int) -> List[Dict[str, Any]]:
        """Fallback: ClinicalTrials.gov legacy API"""
        if expanded_terms and len(expanded_terms) > 0:
            expr = " OR ".join(expanded_terms[:5])
        else:
            expr = search_terms.get("condition", query)

        fields = [
            "NCTId","BriefTitle","OverallStatus","Phase","Condition",
            "InterventionName","LeadSponsorName","StartDate","CompletionDate",
            "EnrollmentCount","LocationCountry"
        ]
        params = {
            "expr": expr,
            "fields": ",".join(fields),
            "min_rnk": 1,
            "max_rnk": max_results,
            "fmt": "JSON",
        }

        print("🌐 Querying ClinicalTrials.gov legacy API...")
        async with httpx.AsyncClient(timeout=20.0) as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
            }
            response = await client.get(self.CTGOV_LEGACY, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()

            studies = data.get("StudyFieldsResponse", {}).get("StudyFields", [])

            results: List[Dict[str, Any]] = []
            for s in studies:
                try:
                    nct_id = (s.get("NCTId") or ["N/A"])[0]
                    title = (s.get("BriefTitle") or ["Untitled Study"])[0]
                    status = (s.get("OverallStatus") or ["Unknown"])[0]
                    phase = (s.get("Phase") or [None])[0]
                    condition = ", ".join(s.get("Condition") or [])
                    intervention = s.get("InterventionName") or [None]
                    intervention = intervention[0] if intervention else None
                    sponsor = (s.get("LeadSponsorName") or [None])[0]
                    start_date = (s.get("StartDate") or [None])[0]
                    completion_date = (s.get("CompletionDate") or [None])[0]
                    enrollment = (s.get("EnrollmentCount") or [None])[0]
                    location = s.get("LocationCountry") or [None]
                    location = location[0] if location else None

                    results.append({
                        "nct_id": nct_id,
                        "title": title,
                        "status": status,
                        "phase": phase,
                        "condition": condition,
                        "intervention": intervention,
                        "sponsor": sponsor,
                        "start_date": start_date,
                        "completion_date": completion_date,
                        "enrollment": enrollment,
                        "location": location,
                        "source_url": f"https://clinicaltrials.gov/study/{nct_id}" if nct_id and nct_id != "N/A" else "",
                        "retrieved_at": datetime.now().isoformat(),
                        "match_score": 0.95,
                        "matched_terms": expanded_terms[:3] if expanded_terms else [query]
                    })
                except Exception:
                    continue

            print(f"✅ ClinicalTrials.gov legacy: {len(results)} trials")
            return results
    
    async def _search_pubmed_clinical_trials(self, query: str, search_terms: dict, expanded_terms: List[str], max_results: int) -> List[Dict[str, Any]]:
        """Search PubMed for clinical trial publications (ENHANCED VERSION)"""
        try:
            search_query = " OR ".join(expanded_terms[:3]) if expanded_terms else search_terms.get("condition", query)
            
            params = {
                "db": "pubmed",
                "term": f"({search_query}) AND (clinical trial[Publication Type] OR randomized controlled trial[Publication Type])",
                "retmax": max_results,
                "retmode": "json"
            }
            
            print(f"🌐 Querying PubMed for clinical trials...")
            
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(self.PUBMED_SEARCH, params=params, headers=self.headers)
                response.raise_for_status()
                data = response.json()
                id_list = data.get("esearchresult", {}).get("idlist", [])
                
                if id_list:
                    trials = await self._fetch_pubmed_details(id_list[:max_results])
                    print(f"✅ PubMed: {len(trials)} clinical trial publications")
                    return trials
                else:
                    print(f"⚠️ PubMed: No results found")
                    return []
                    
        except Exception as e:
            print(f"⚠️ PubMed error: {e}")
            return []
    
    async def _fetch_pubmed_details(self, id_list: List[str]) -> List[Dict[str, Any]]:
        """Fetch detailed info for PubMed articles"""
        try:
            params = {
                "db": "pubmed",
                "id": ",".join(id_list),
                "retmode": "json"
            }
            
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(self.PUBMED_SUMMARY, params=params, headers=self.headers)
                response.raise_for_status()
                data = response.json()
                results = []
                
                for pmid, article in data.get("result", {}).items():
                    if pmid == "uids":
                        continue
                        
                    try:
                        # Extract authors
                        authors = article.get("authors", [])
                        author_str = ", ".join([a.get("name", "") for a in authors[:3]]) if authors else "Unknown"
                        
                        results.append({
                            "nct_id": f"PMID{pmid}",
                            "title": article.get("title", "Untitled"),
                            "status": "PUBLISHED",
                            "phase": None,
                            "condition": article.get("fulljournalname", ""),
                            "intervention": None,
                            "sponsor": author_str,
                            "start_date": article.get("pubdate", ""),
                            "completion_date": None,
                            "enrollment": None,
                            "location": None,
                            "source_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                            "retrieved_at": datetime.now().isoformat(),
                            "match_score": 0.8,
                            "matched_terms": []
                        })
                    except Exception:
                        continue
                
                return results
                    
        except Exception as e:
            print(f"⚠️ Error fetching PubMed details: {e}")
            return []
    
    def _extract_keywords(self, query: str) -> Dict[str, str]:
        """Extract search keywords from natural language query"""
        query_lower = query.lower()
        keywords = {}
        
        # Common disease categories
        diseases = ["respiratory", "cardiovascular", "diabetes", "cancer", "asthma", 
                   "copd", "pneumonia", "tuberculosis", "covid", "influenza", "hypertension"]
        for disease in diseases:
            if disease in query_lower:
                keywords["condition"] = disease
                break
        
        # Location extraction
        locations = ["india", "united states", "china", "europe", "asia", "africa", "uk", "usa"]
        for location in locations:
            if location in query_lower:
                keywords["location"] = location
                break
        
        if "condition" not in keywords:
            keywords["condition"] = query
        
        return keywords
    
    def _parse_study(self, study: Dict[str, Any]) -> ClinicalTrialResult:
        """Parse a study from ClinicalTrials.gov v2 API response"""
        protocol = study.get("protocolSection", {})
        identification = protocol.get("identificationModule", {})
        status_module = protocol.get("statusModule", {})
        design = protocol.get("designModule", {})
        conditions = protocol.get("conditionsModule", {})
        interventions = protocol.get("armsInterventionsModule", {})
        sponsor = protocol.get("sponsorCollaboratorsModule", {})
        contacts = protocol.get("contactsLocationsModule", {})
        
        enrollment_info = design.get("enrollmentInfo", {})
        enrollment = enrollment_info.get("count")
        
        phases = design.get("phases", [])
        phase = phases[0] if phases else None
        
        intervention_list = interventions.get("interventions", [])
        intervention = intervention_list[0].get("name") if intervention_list else None
        
        lead_sponsor = sponsor.get("leadSponsor", {})
        sponsor_name = lead_sponsor.get("name")
        
        locations = contacts.get("locations", [])
        location = locations[0].get("country") if locations else None
        
        nct_id = identification.get("nctId", "N/A")
        source_url = f"https://clinicaltrials.gov/study/{nct_id}" if nct_id != "N/A" else ""
        
        return ClinicalTrialResult(
            nct_id=nct_id,
            title=identification.get("briefTitle", "Untitled Study"),
            status=status_module.get("overallStatus", "Unknown"),
            phase=phase,
            condition=", ".join(conditions.get("conditions", [])),
            intervention=intervention,
            sponsor=sponsor_name,
            start_date=status_module.get("startDateStruct", {}).get("date"),
            completion_date=status_module.get("completionDateStruct", {}).get("date"),
            enrollment=enrollment,
            location=location,
            source_url=source_url,
            retrieved_at=datetime.now().isoformat()
        )
    
    async def analyze_competition(self, results: List[ClinicalTrialResult]) -> Dict[str, Any]:
        """Analyze competition level from trial data"""
        if not results:
            return {"competition_level": "unknown", "active_trials": 0}
        
        active_statuses = ["RECRUITING", "ACTIVE_NOT_RECRUITING", "ENROLLING_BY_INVITATION", "ACTIVE"]
        active_count = sum(1 for r in results if r.status.upper() in active_statuses)
        
        phase_dist = {}
        for r in results:
            if r.phase:
                phase_dist[r.phase] = phase_dist.get(r.phase, 0) + 1
        
        if active_count < 5:
            competition = "low"
        elif active_count < 15:
            competition = "medium"
        else:
            competition = "high"
        
        return {
            "competition_level": competition,
            "active_trials": active_count,
            "total_trials": len(results),
            "phase_distribution": phase_dist,
            "published_results": sum(1 for r in results if r.status == "PUBLISHED")
        }
