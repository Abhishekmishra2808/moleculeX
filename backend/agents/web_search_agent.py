"""
Web Search Agent - DuckDuckGo Instant Answer + Wikipedia Search
Enhanced with rate limiting, error handling, and API best practices
"""
import httpx
import asyncio
from typing import List, Dict, Any
from models import WebIntelResult
from datetime import datetime


class WebSearchAgent:
    """General web search using DuckDuckGo Instant Answers and Wikipedia"""
    
    name = "Web Search Agent"
    DDG_URL = "https://api.duckduckgo.com/"
    WIKI_URL = "https://en.wikipedia.org/w/api.php"
    
    def __init__(self, user_agent: str = None):
        """
        Initialize Web Search Agent
        
        Args:
            user_agent: Custom User-Agent string (recommended for Wikipedia)
        """
        self.user_agent = user_agent or "MoleculeX-Research/1.0 (Educational; https://github.com/yourusername/moleculex)"
        
        # Wikipedia API best practices headers
        self.wiki_headers = {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate",  # Enable compression
            "Accept": "application/json",
        }
        
        # DuckDuckGo headers
        self.ddg_headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }

    async def search(self, query: str, max_results: int = 20, expanded_terms: List[str] = None) -> List[WebIntelResult]:
        """
        Search both DuckDuckGo and Wikipedia for general web intelligence
        
        Args:
            query: Search query
            max_results: Maximum results to return
            expanded_terms: Optional expanded query terms
        """
        print(f"🔍 {self.name}: Searching for '{query}'")
        
        # Use expanded terms if provided
        search_query = " ".join(expanded_terms[:5]) if expanded_terms else query
        
        tasks = [
            self._search_duckduckgo_safe(search_query, max_results // 2 or 1),
            self._search_wikipedia(search_query, max_results // 2 or 1),
        ]
        
        results_lists = await asyncio.gather(*tasks, return_exceptions=True)
        
        results: List[WebIntelResult] = []
        for r in results_lists:
            if isinstance(r, Exception):
                print(f"⚠️ Error from one source: {r}")
                continue
            if isinstance(r, list):
                results.extend(r)
        
        # Deduplicate by URL
        seen_urls = set()
        unique_results = []
        for result in results:
            if result.url not in seen_urls:
                seen_urls.add(result.url)
                unique_results.append(result)
        
        print(f"✅ {self.name}: Found {len(unique_results)} unique results")
        return unique_results[:max_results]

    async def _search_duckduckgo_safe(self, query: str, limit: int) -> List[WebIntelResult]:
        """
        DuckDuckGo with rate limit protection and retry logic
        Note: DDG Instant Answer API is NOT a full search API - returns limited instant answers
        """
        max_retries = 2
        for attempt in range(max_retries):
            try:
                await asyncio.sleep(1.0)  # Rate limiting: 1 second between requests
                
                results = await self._search_duckduckgo(query, limit)
                
                if results:
                    return results
                elif attempt < max_retries - 1:
                    # If no results, wait longer and retry
                    print(f"ℹ️ DDG returned no results, retrying...")
                    await asyncio.sleep(2.0)
                    continue
                else:
                    return []
                    
            except Exception as e:
                if "202" in str(e) or "ratelimit" in str(e).lower():
                    print(f"⚠️ DDG rate limit hit (attempt {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(3.0)  # Wait longer on rate limit
                        continue
                else:
                    print(f"⚠️ DDG error: {e}")
                    
                if attempt == max_retries - 1:
                    return []
        
        return []

    async def _search_duckduckgo(self, query: str, limit: int) -> List[WebIntelResult]:
        """
        Search DuckDuckGo Instant Answer API
        Note: This is NOT a full search results API - it returns instant answers and related topics
        """
        params = {
            "q": query,
            "format": "json",
            "no_html": 1,
            "skip_disambig": 1,
            "t": "moleculex",  # Optional app identifier
        }
        
        try:
            print("🔍 Querying DuckDuckGo Instant Answer...")
            
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(self.DDG_URL, params=params, headers=self.ddg_headers)
                
                if resp.status_code == 202:
                    raise Exception("DDG Rate limit (202)")
                
                if resp.status_code != 200:
                    print(f"⚠️ DDG returned {resp.status_code}")
                    return []
                
                data = resp.json()
                results: List[WebIntelResult] = []
                
                # Process Instant Answer (if available)
                abstract_text = data.get("AbstractText") or data.get("Abstract")
                abstract_url = data.get("AbstractURL")
                abstract_source = data.get("AbstractSource") or "DuckDuckGo"
                heading = data.get("Heading") or data.get("Answer") or query
                
                if abstract_text and abstract_url:
                    results.append(WebIntelResult(
                        source=abstract_source,
                        title=heading[:150],
                        url=abstract_url,
                        snippet=str(abstract_text)[:300],
                        relevance_score=0.85,  # Instant answers are highly relevant
                        retrieved_at=datetime.now().isoformat(),
                    ))
                
                # Process Answer (direct answer box)
                answer = data.get("Answer")
                answer_type = data.get("AnswerType")
                if answer and answer_type:
                    results.append(WebIntelResult(
                        source="DuckDuckGo Answer",
                        title=f"{answer_type}: {query}"[:150],
                        url="https://duckduckgo.com",
                        snippet=str(answer)[:300],
                        relevance_score=0.9,
                        retrieved_at=datetime.now().isoformat(),
                    ))
                
                # Process Related Topics (most valuable for general searches)
                topics = data.get("RelatedTopics", [])
                count = len(results)
                
                for t in topics:
                    if count >= limit:
                        break
                        
                    # Direct topic
                    if isinstance(t, dict) and t.get("FirstURL") and t.get("Text"):
                        results.append(WebIntelResult(
                            source="DuckDuckGo",
                            title=t.get("Text", "")[:150],
                            url=t.get("FirstURL"),
                            snippet=t.get("Text", "")[:300],
                            relevance_score=0.7,
                            retrieved_at=datetime.now().isoformat(),
                        ))
                        count += 1
                    
                    # Nested topics
                    elif isinstance(t, dict) and t.get("Topics"):
                        for s in t.get("Topics", []):
                            if count >= limit:
                                break
                            if s.get("FirstURL") and s.get("Text"):
                                results.append(WebIntelResult(
                                    source="DuckDuckGo",
                                    title=s.get("Text", "")[:150],
                                    url=s.get("FirstURL"),
                                    snippet=s.get("Text", "")[:300],
                                    relevance_score=0.65,
                                    retrieved_at=datetime.now().isoformat(),
                                ))
                                count += 1
                
                # Process Results (external links)
                results_data = data.get("Results", [])
                for r in results_data:
                    if count >= limit:
                        break
                    if r.get("FirstURL") and r.get("Text"):
                        results.append(WebIntelResult(
                            source="DuckDuckGo",
                            title=r.get("Text", "")[:150],
                            url=r.get("FirstURL"),
                            snippet=r.get("Text", "")[:300],
                            relevance_score=0.75,
                            retrieved_at=datetime.now().isoformat(),
                        ))
                        count += 1
                
                print(f"✅ DuckDuckGo: {len(results)} results")
                return results
                
        except Exception as e:
            print(f"⚠️ DuckDuckGo error: {e}")
            return []

    async def _search_wikipedia(self, query: str, limit: int) -> List[WebIntelResult]:
        """
        Search Wikipedia using MediaWiki API with best practices
        Implements etiquette: User-Agent, compression, batch requests
        """
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "formatversion": "2",  # Use modern format
            "srlimit": limit,
            "srprop": "snippet|titlesnippet|timestamp|wordcount",  # Request multiple properties
        }
        
        try:
            print("🔍 Querying Wikipedia...")
            await asyncio.sleep(0.5)  # Courtesy delay
            
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(self.WIKI_URL, params=params, headers=self.wiki_headers)
                resp.raise_for_status()
                
                data = resp.json()
                search_results = data.get("query", {}).get("search", [])
                
                if not search_results:
                    print("ℹ️ Wikipedia: No results found")
                    return []
                
                results: List[WebIntelResult] = []
                
                for item in search_results[:limit]:
                    try:
                        title = item.get("title", "Untitled")
                        pageid = item.get("pageid")
                        
                        # Clean snippet (remove HTML tags)
                        snippet = item.get("snippet", "")
                        snippet = snippet.replace("<span class=\"searchmatch\">", "")
                        snippet = snippet.replace("</span>", "")
                        snippet = snippet.replace("&quot;", '"')
                        
                        # Construct URL
                        url = f"https://en.wikipedia.org/?curid={pageid}" if pageid else f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
                        
                        # Calculate relevance based on word count (longer articles are often more authoritative)
                        wordcount = item.get("wordcount", 0)
                        relevance_score = min(0.6 + (wordcount / 10000), 0.95)
                        
                        results.append(WebIntelResult(
                            source="Wikipedia",
                            title=title[:150],
                            url=url,
                            snippet=snippet[:300] + ("..." if len(snippet) > 300 else ""),
                            relevance_score=round(relevance_score, 2),
                            retrieved_at=datetime.now().isoformat(),
                        ))
                    except Exception as e:
                        continue
                
                print(f"✅ Wikipedia: {len(results)} results")
                return results
                
        except Exception as e:
            print(f"⚠️ Wikipedia error: {e}")
            return []
    
    async def get_wikipedia_summary(self, title: str) -> Dict[str, Any]:
        """
        Get full summary of a Wikipedia article
        
        Args:
            title: Wikipedia article title
        """
        params = {
            "action": "query",
            "prop": "extracts|info",
            "exintro": True,  # Only intro section
            "explaintext": True,  # Plain text
            "titles": title,
            "format": "json",
            "formatversion": "2",
            "inprop": "url",
        }
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(self.WIKI_URL, params=params, headers=self.wiki_headers)
                resp.raise_for_status()
                
                data = resp.json()
                pages = data.get("query", {}).get("pages", [])
                
                if not pages:
                    return {"error": "Page not found"}
                
                page = pages[0]
                
                return {
                    "title": page.get("title", ""),
                    "extract": page.get("extract", ""),
                    "url": page.get("fullurl", ""),
                    "pageid": page.get("pageid"),
                }
                
        except Exception as e:
            return {"error": str(e)}
    
    async def get_wikipedia_batch(self, titles: List[str]) -> List[Dict[str, Any]]:
        """
        Get summaries for multiple Wikipedia articles in one request
        Uses pipe character (|) as recommended by MediaWiki API etiquette
        
        Args:
            titles: List of Wikipedia article titles
        """
        # MediaWiki recommends using pipe separator for batch requests
        titles_str = "|".join(titles[:50])  # API limit is 50 titles
        
        params = {
            "action": "query",
            "prop": "extracts|info",
            "exintro": True,
            "explaintext": True,
            "titles": titles_str,
            "format": "json",
            "formatversion": "2",
            "inprop": "url",
        }
        
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(self.WIKI_URL, params=params, headers=self.wiki_headers)
                resp.raise_for_status()
                
                data = resp.json()
                pages = data.get("query", {}).get("pages", [])
                
                results = []
                for page in pages:
                    results.append({
                        "title": page.get("title", ""),
                        "extract": page.get("extract", "")[:500],
                        "url": page.get("fullurl", ""),
                        "pageid": page.get("pageid"),
                    })
                
                return results
                
        except Exception as e:
            print(f"⚠️ Wikipedia batch error: {e}")
            return []
