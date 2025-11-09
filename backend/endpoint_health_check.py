#!/usr/bin/env python3
"""
Endpoint Health Check — Alternative Clinical Trial APIs
"""
import asyncio
import httpx
import time
from typing import Any, Dict

print("=== CLINICAL TRIAL API ALTERNATIVES ===\n")

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}
TIMEOUT = 20.0
RETRIES = 2
RETRY_DELAY = 1.0
REQUEST_DELAY = 1.5  # seconds between requests

ENDPOINTS = [
    {
        "name": "Europe PMC (Clinical Trials)",
        "url": "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
        "method": "GET",
        "params": {"query": "clinical trial cancer", "format": "json", "pageSize": 5},
        "expect_key": "resultList",
    },
    {
        "name": "PubMed (NCBI E-utilities)",
        "url": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        "method": "GET",
        "params": {
            "db": "pubmed",
            "term": "cancer clinical trial",
            "retmode": "json",
            "retmax": 5
        },
        "expect_key": "esearchresult",
    },
    {
        "name": "PubMed Central (PMC)",
        "url": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        "method": "GET",
        "params": {
            "db": "pmc",
            "term": "clinical trial",
            "retmode": "json",
            "retmax": 5
        },
        "expect_key": "esearchresult",
    },
    {
        "name": "NCBI Database List",
        "url": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/einfo.fcgi",
        "method": "GET",
        "params": {"retmode": "json"},
        "expect_key": "einforesult",
    },
    {
        "name": "DuckDuckGo (Clinical Trials)",
        "url": "https://api.duckduckgo.com/",
        "method": "GET",
        "params": {"q": "clinical trials cancer", "format": "json", "no_html": 1},
        "expect_key": "AbstractText",
    },
    {
        "name": "Wikipedia (Clinical Trials)",
        "url": "https://en.wikipedia.org/w/api.php",
        "method": "GET",
        "params": {
            "action": "query",
            "list": "search",
            "srsearch": "clinical trial",
            "format": "json"
        },
        "expect_key": "query",
    },
    {
        "name": "Crossref API (Clinical Research)",
        "url": "https://api.crossref.org/works",
        "method": "GET",
        "params": {
            "query": "clinical trial cancer",
            "rows": 5
        },
        "expect_key": "message",
    },
]


def find_key_recursive(obj: Any, key: str) -> bool:
    """Recursively search for a key in nested dict/list structures."""
    if isinstance(obj, dict):
        if key in obj:
            return True
        return any(find_key_recursive(v, key) for v in obj.values())
    if isinstance(obj, list):
        return any(find_key_recursive(i, key) for i in obj)
    return False


async def request_with_retries(client: httpx.AsyncClient, method: str, url: str, params=None, json_body=None, headers=None):
    """Make HTTP request with retry logic."""
    last_exc = None
    for attempt in range(RETRIES + 1):
        try:
            if method == "GET":
                resp = await client.get(url, params=params, headers=headers, timeout=TIMEOUT)
                return resp
            elif method == "POST":
                resp = await client.post(url, params=params, json=json_body, headers=headers, timeout=TIMEOUT)
                return resp
            else:
                raise ValueError(f"Unsupported method: {method}")
        except (httpx.TransportError, httpx.ReadTimeout) as e:
            last_exc = e
            if attempt < RETRIES:
                await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                continue
            raise
    raise last_exc


async def check_endpoint(client: httpx.AsyncClient, ep: Dict[str, Any]) -> Dict[str, Any]:
    """Check health of a single endpoint."""
    start = time.time()
    method = ep.get("method", "GET").upper()
    params = ep.get("params")
    json_body = ep.get("json")
    headers = ep.get("headers", {})

    try:
        resp = await request_with_retries(client, method, ep["url"], params=params, json_body=json_body, headers=headers)
        elapsed = round((time.time() - start) * 1000)
        status = resp.status_code
        snippet = resp.text[:2000]

        contains_expected = False
        if "expect_key" in ep:
            try:
                j = resp.json()
                key = ep["expect_key"]
                if isinstance(j, dict) and key in j:
                    contains_expected = True
                else:
                    contains_expected = find_key_recursive(j, key)
            except Exception:
                contains_expected = False
        elif "expect_text" in ep:
            contains_expected = ep["expect_text"].lower() in snippet.lower()
        else:
            contains_expected = status == 200

        ok = (status == 200) and contains_expected
        error = None if ok else (f"HTTP {status}" if status != 200 else snippet[:300])

        return {
            "name": ep["name"],
            "status_code": status,
            "ms": elapsed,
            "ok": ok,
            "contains_expected": contains_expected,
            "error": error,
        }

    except Exception as e:
        elapsed = round((time.time() - start) * 1000)
        return {
            "name": ep["name"],
            "status_code": None,
            "ms": elapsed,
            "ok": False,
            "contains_expected": False,
            "error": str(e)[:400],
        }


async def main():
    """Run health checks on all endpoints with rate limiting."""
    async with httpx.AsyncClient(headers=DEFAULT_HEADERS, verify=True, follow_redirects=True) as client:
        results = []
        
        for i, ep in enumerate(ENDPOINTS):
            print(f"[{i+1}/{len(ENDPOINTS)}] Testing {ep['name']}...", end=" ", flush=True)
            result = await check_endpoint(client, ep)
            results.append(result)
            
            status_icon = "✓" if result["ok"] else "✗"
            print(f"{status_icon} {result['status_code']} ({result['ms']}ms)")
            
            if i < len(ENDPOINTS) - 1:
                await asyncio.sleep(REQUEST_DELAY)
    
    print(f"\n{'='*70}")
    print("Endpoint Health Check Results:")
    print(f"{'='*70}\n")
    
    passed = 0
    failed = 0
    
    for r in results:
        status_icon = "✓ PASS" if r["ok"] else "✗ FAIL"
        print(f"{status_icon} | {r['name']}: {r['status_code']} | {r['ms']}ms | expected={r['contains_expected']}")
        if r['error']:
            print(f"  └─ Error: {r['error'][:200]}")
        
        if r["ok"]:
            passed += 1
        else:
            failed += 1
    
    print(f"\n{'='*70}")
    print(f"Summary: {passed} passed, {failed} failed out of {len(results)} endpoints")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    asyncio.run(main())
