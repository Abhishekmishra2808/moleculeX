"""
Web Intelligence Worker Agent - Multi-Source Literature & Research Integration
Sources integrated (all keyless):
 - Europe PMC (core results)
 - PubMed (E-utilities esearch + esummary - updated Nov 2022)
 - PubMed Central (PMC) via esearch/esummary
 - Crossref (DOI metadata - rate limit updates Dec 2025)
"""
import httpx
import asyncio
from typing import List, Dict, Any
from models import WebIntelResult
from datetime import datetime


class WebIntelAgent:
    """Agent for gathering scientific & clinical research literature from multiple open APIs"""

    EUROPEPMC_BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    PUBMED_ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    PMC_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    CROSSREF_WORKS = "https://api.crossref.org/works"
    
    def __init__(self, contact_email: str = None):
        """
        Initialize Web Intel Agent
        
        Args:
            contact_email: Optional email for Crossref polite pool (10x higher rate limit)
        """
        self.name = "Web Intel Agent"
        self.contact_email = contact_email
        
        # Headers for polite Crossref access (10x rate limit boost)
        self.crossref_headers = {
            "User-Agent": f"MoleculeX-Research/1.0 (mailto:{contact_email})" if contact_email else "MoleculeX-Research/1.0",
        }
        
        # NCBI E-utilities best practices headers
        self.ncbi_headers = {
            "User-Agent": "MoleculeX-Research/1.0",
        }
    
    async def search(self, query: str, max_results: int = 20, expanded_terms: List[str] = None) -> List[WebIntelResult]:
        """Aggregate literature from Europe PMC, PubMed, PMC, and Crossref concurrently."""
        print(f"🌐 {self.name}: Starting multi-source literature search for '{query}'")
        if expanded_terms:
            print(f"📋 Using expanded terms: {expanded_terms[:8]}")

        # Determine keyword string
        if expanded_terms:
            keywords = " OR ".join(expanded_terms[:8])
        else:
            keywords = self._extract_keywords(query)

        # Split max_results allocation across sources (EuropePMC gets largest share)
        epmc_limit = max(min(10, max_results), 5)
        per_other = max(3, max_results // 5)

        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            tasks = [
                self._search_europe_pmc(client, keywords, epmc_limit),
                self._search_pubmed(client, keywords, per_other),
                self._search_pmc(client, keywords, per_other),
                self._search_crossref(client, keywords, per_other),
            ]
            results_lists = await asyncio.gather(*tasks, return_exceptions=True)

        combined: List[WebIntelResult] = []
        for lst in results_lists:
            if isinstance(lst, Exception):
                print(f"⚠️ Error from one source: {lst}")
                continue
            if isinstance(lst, list):
                combined.extend(lst)
                
        # Deduplicate by title+url
        seen = set()
        unique: List[WebIntelResult] = []
        for r in combined:
            key = (r.title.lower().strip(), r.url)
            if key not in seen:
                seen.add(key)
                unique.append(r)
                
        # Sort by relevance score
        unique.sort(key=lambda x: x.relevance_score, reverse=True)
        
        print(f"✅ {self.name}: Aggregated {len(unique)} unique publications from all sources")
        return unique[:max_results]

    async def _search_europe_pmc(self, client: httpx.AsyncClient, keywords: str, limit: int) -> List[WebIntelResult]:
        """Search Europe PMC - primary source for biomedical literature"""
        params = {
            "query": keywords,
            "format": "json",
            "pageSize": limit,
            "sort": "CITED desc",  # Sort by citation count for quality
            "resultType": "core",
            "synonym": "true",  # Enable MeSH synonym expansion
        }
        try:
            print("🔍 Querying Europe PMC...")
            await asyncio.sleep(0.3)  # Rate limiting
            
            resp = await client.get(self.EUROPEPMC_BASE, params=params, headers=self.ncbi_headers)
            resp.raise_for_status()
            
            data = resp.json()
            items = data.get("resultList", {}).get("result", [])
            results = []
            
            for item in items:
                try:
                    results.append(self._parse_publication(item))
                except Exception as e:
                    continue
                    
            print(f"✅ Europe PMC: {len(results)} publications")
            return results
            
        except Exception as e:
            print(f"⚠️ Europe PMC error: {e}")
            return []

    async def _search_pubmed(self, client: httpx.AsyncClient, keywords: str, limit: int) -> List[WebIntelResult]:
        """Search PubMed using updated E-utilities (Nov 2022 version)"""
        # Updated API with relevance sorting
        params = {
            "db": "pubmed",
            "term": f"({keywords}) AND (clinical trial[Publication Type] OR systematic review[Publication Type])",
            "retmode": "json",
            "retmax": limit,
            "sort": "relevance",  # Use new relevance sorting (Nov 2022 update)
            "usehistory": "n",
        }
        try:
            print("🔍 Querying PubMed...")
            await asyncio.sleep(0.35)  # NCBI recommends 3 requests/sec max
            
            r = await client.get(self.PUBMED_ESEARCH, params=params, headers=self.ncbi_headers)
            r.raise_for_status()
            
            data = r.json()
            ids = data.get("esearchresult", {}).get("idlist", [])
            
            if not ids:
                print("ℹ️ PubMed: No results found")
                return []
                
            results = await self._fetch_pubmed_summaries(client, ids, "pubmed")
            print(f"✅ PubMed: {len(results)} publications")
            return results
            
        except Exception as e:
            print(f"⚠️ PubMed error: {e}")
            return []

    async def _search_pmc(self, client: httpx.AsyncClient, keywords: str, limit: int) -> List[WebIntelResult]:
        """Search PubMed Central (full-text articles)"""
        params = {
            "db": "pmc",
            "term": f"({keywords}) AND (clinical trial OR randomized controlled trial)",
            "retmode": "json",
            "retmax": limit,
            "sort": "relevance",
        }
        try:
            print("🔍 Querying PMC...")
            await asyncio.sleep(0.35)  # NCBI rate limiting
            
            r = await client.get(self.PMC_ESEARCH, params=params, headers=self.ncbi_headers)
            r.raise_for_status()
            
            ids = r.json().get("esearchresult", {}).get("idlist", [])
            
            if not ids:
                print("ℹ️ PMC: No results found")
                return []
                
            results = await self._fetch_pubmed_summaries(client, ids, "pmc")
            print(f"✅ PMC: {len(results)} publications")
            return results
            
        except Exception as e:
            print(f"⚠️ PMC error: {e}")
            return []

    async def _fetch_pubmed_summaries(self, client: httpx.AsyncClient, ids: List[str], db: str) -> List[WebIntelResult]:
        """Fetch summaries for PubMed/PMC IDs"""
        params = {
            "db": db,
            "id": ",".join(ids),
            "retmode": "json",
            "rettype": "abstract",
        }
        results: List[WebIntelResult] = []
        
        try:
            await asyncio.sleep(0.35)  # NCBI rate limiting
            
            r = await client.get(self.PUBMED_ESUMMARY, params=params, headers=self.ncbi_headers)
            r.raise_for_status()
            
            data = r.json().get("result", {})
            
            for pid, article in data.items():
                if pid == "uids":
                    continue
                    
                try:
                    title = article.get("title", "Untitled")
                    
                    # Get abstract if available
                    abstract = ""
                    if "abstract" in article:
                        abstract = article["abstract"]
                    
                    # Get publication date
                    pub_date = article.get("pubdate", "") or article.get("sortpubdate", "")
                    
                    # Get authors
                    authors = article.get("authors", [])
                    author_str = ", ".join([a.get("name", "") for a in authors[:3]]) if authors else ""
                    
                    # Create snippet
                    snippet = abstract[:300] + "..." if abstract and len(abstract) > 300 else (abstract or f"Published: {pub_date}")
                    if author_str:
                        snippet = f"{author_str}. {snippet}"
                    
                    # Determine URL
                    if db == "pubmed":
                        url = f"https://pubmed.ncbi.nlm.nih.gov/{pid}/"
                        source = "PubMed"
                    else:
                        url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pid}/"
                        source = "PMC"
                    
                    results.append(WebIntelResult(
                        source=source,
                        title=title[:150],
                        url=url,
                        snippet=snippet[:300],
                        relevance_score=0.75,  # PubMed/PMC are high quality
                        retrieved_at=datetime.now().isoformat(),
                    ))
                except Exception:
                    continue
                    
        except Exception as e:
            print(f"⚠️ Error fetching {db} summaries: {e}")
            
        return results

    async def _search_crossref(self, client: httpx.AsyncClient, keywords: str, limit: int) -> List[WebIntelResult]:
        """
        Search Crossref DOI database
        Note: Rate limits changed Dec 1, 2025 - using polite pool for better limits
        """
        params = {
            "query": f"{keywords} clinical trial",
            "rows": limit,
            "filter": "has-abstract:true,type:journal-article",
            "sort": "relevance",
        }
        try:
            print("🔍 Querying Crossref...")
            await asyncio.sleep(1.0)  # Crossref rate limiting (updated Dec 2025)
            
            r = await client.get(self.CROSSREF_WORKS, params=params, headers=self.crossref_headers)
            r.raise_for_status()
            
            items = r.json().get("message", {}).get("items", [])
            results: List[WebIntelResult] = []
            
            for item in items:
                try:
                    title_list = item.get("title", [])
                    title = title_list[0] if title_list else "Untitled"
                    
                    doi = item.get("DOI")
                    url = item.get("URL") or (f"https://doi.org/{doi}" if doi else "")
                    
                    # Clean abstract
                    abstract = (item.get("abstract") or "").replace("<jats:p>", "").replace("</jats:p>", "").replace("<jats:italic>", "").replace("</jats:italic>", "")
                    snippet = abstract[:300] + ("..." if len(abstract) > 300 else "") if abstract else "No abstract available."
                    
                    # Get citation count for relevance scoring
                    is_referenced_by_count = item.get("is-referenced-by-count", 0)
                    relevance_score = min(0.5 + (is_referenced_by_count / 200), 0.95)
                    
                    # Get journal info
                    container_title = item.get("container-title", [])
                    source = container_title[0] if container_title else "Crossref"
                    
                    results.append(WebIntelResult(
                        source=source,
                        title=title[:150],
                        url=url,
                        snippet=snippet,
                        relevance_score=round(relevance_score, 2),
                        retrieved_at=datetime.now().isoformat(),
                    ))
                except Exception:
                    continue
                    
            print(f"✅ Crossref: {len(results)} publications")
            return results
            
        except Exception as e:
            print(f"⚠️ Crossref error: {e}")
            return []
    
    def _parse_publication(self, item: Dict[str, Any]) -> WebIntelResult:
        """Parse publication data from Europe PMC response"""
        
        # Get publication ID and construct URL
        pmid = item.get("pmid")
        pmcid = item.get("pmcid")
        doi = item.get("doi")
        
        # Construct URL (prefer PMC full text, then PubMed, then DOI)
        if pmcid:
            url = f"https://europepmc.org/article/PMC/{pmcid}"
        elif pmid:
            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        elif doi:
            url = f"https://doi.org/{doi}"
        else:
            url = "https://europepmc.org/"
        
        # Get title
        title = item.get("title", "Untitled Publication")
        if len(title) > 150:
            title = title[:147] + "..."
        
        # Get abstract snippet
        abstract = item.get("abstractText", "")
        if abstract:
            snippet = abstract[:300] + "..." if len(abstract) > 300 else abstract
        else:
            snippet = item.get("summary", "No abstract available.")[:300]
        
        # Get source/journal
        source = item.get("journalTitle") or item.get("source") or "Europe PMC"
        
        # Calculate relevance score based on citation count and publication type
        citation_count = item.get("citedByCount", 0)
        pub_type = item.get("pubType", "")
        
        # Base score from citations (log scale)
        base_score = min(0.5 + (citation_count / 1000), 0.9)
        
        # Boost for systematic reviews and meta-analyses
        if "review" in pub_type.lower() or "meta-analysis" in pub_type.lower():
            base_score = min(base_score + 0.1, 1.0)
        
        relevance_score = round(base_score, 2)
        
        return WebIntelResult(
            source=source,
            title=title,
            url=url,
            snippet=snippet,
            relevance_score=relevance_score,
            retrieved_at=datetime.now().isoformat()
        )
    
    def _extract_keywords(self, query: str) -> str:
        """Extract search keywords from natural language query (broad terms)."""
        query_lower = query.lower()
        
        # Medical condition keywords with enhanced search terms
        conditions = {
            "respiratory": "respiratory disease OR pulmonary OR lung OR bronchial",
            "cardiovascular": "cardiovascular OR cardiac OR heart disease OR coronary",
            "diabetes": "diabetes OR diabetic OR glycemic OR insulin resistance",
            "cancer": "cancer OR oncology OR tumor OR neoplasm OR malignancy",
            "asthma": "asthma OR bronchial hyperreactivity OR airway inflammation",
            "copd": "COPD OR chronic obstructive pulmonary disease OR emphysema",
            "hypertension": "hypertension OR high blood pressure OR arterial pressure",
            "alzheimer": "Alzheimer OR dementia OR cognitive decline OR neurodegeneration",
            "tuberculosis": "tuberculosis OR TB OR mycobacterium tuberculosis",
            "covid": "COVID-19 OR SARS-CoV-2 OR coronavirus",
        }
        
        # Check for matching conditions
        for key, search_term in conditions.items():
            if key in query_lower:
                return search_term
        
        # Extract key terms from query
        words = query_lower.split()
        stop_words = {
            "what", "which", "how", "are", "the", "a", "an", "in", "on", 
            "at", "for", "to", "of", "with", "show", "tell", "about", "find",
            "search", "look", "get", "give", "me"
        }
        keywords = [w for w in words if w not in stop_words and len(w) > 3]
        
        return " ".join(keywords[:5]) if keywords else "pharmaceutical research"
    
    async def get_full_text(self, pmcid: str) -> Dict[str, Any]:
        """
        Fetch full text of an article from PMC if available
        
        Args:
            pmcid: PubMed Central ID (e.g., "PMC1234567")
        """
        try:
            efetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
            params = {
                "db": "pmc",
                "id": pmcid.replace("PMC", ""),
                "rettype": "xml",
            }
            
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(efetch_url, params=params, headers=self.ncbi_headers)
                resp.raise_for_status()
                
                return {
                    "pmcid": pmcid,
                    "full_text_xml": resp.text,
                    "available": True
                }
                
        except Exception as e:
            return {
                "pmcid": pmcid,
                "error": str(e),
                "available": False
            }
