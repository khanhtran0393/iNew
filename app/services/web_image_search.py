"""
Web Image Search Service - Fetches real images from search engines (Bing, DuckDuckGo, Google)
for editorial/news content.
"""
import asyncio
import logging
import re
import urllib.parse
from typing import List, Dict, Any, Optional
import httpx
from bs4 import BeautifulSoup

from app.config import settings

logger = logging.getLogger("ak_news.web_image_search")

# Search engine configurations
SEARCH_ENGINES = {
    "bing": {
        "url": "https://www.bing.com/images/search",
        "params": {"q": "{query}", "form": "HDRSC2", "first": "1", "count": "20"},
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        }
    },
    "duckduckgo": {
        "url": "https://duckduckgo.com/",
        "params": {"q": "{query}", "t": "h_", "iax": "images", "ia": "images"},
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        }
    },
    "google": {
        "url": "https://www.google.com/search",
        "params": {"q": "{query}", "tbm": "isch", "hl": "vi"},
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        }
    }
}


async def search_web_images(query: str, engine: str = "bing", max_results: int = 20) -> List[Dict[str, Any]]:
    """
    Search for images on the web using specified search engine.
    Returns list of image results with URL, thumbnail, source, title, etc.
    """
    if engine not in SEARCH_ENGINES:
        engine = "bing"
    
    config = SEARCH_ENGINES[engine]
    encoded_query = urllib.parse.quote(query)
    
    params = {}
    for k, v in config["params"].items():
        params[k] = v.replace("{query}", encoded_query)
    
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(config["url"], params=params, headers=config["headers"])
            
            if resp.status_code != 200:
                logger.warning(f"{engine} search failed: {resp.status_code}")
                return []
            
            html = resp.text
            return parse_image_results(html, engine, max_results)
            
    except Exception as e:
        logger.error(f"Web image search error ({engine}): {e}")
        return []


def parse_image_results(html: str, engine: str, max_results: int) -> List[Dict[str, Any]]:
    """Parse HTML response from search engine to extract image URLs and metadata."""
    soup = BeautifulSoup(html, "html.parser")
    results = []
    
    if engine == "bing":
        results = parse_bing_images(soup, max_results)
    elif engine == "duckduckgo":
        results = parse_duckduckgo_images(soup, max_results)
    elif engine == "google":
        results = parse_google_images(soup, max_results)
    
    return results[:max_results]


def parse_bing_images(soup: BeautifulSoup, max_results: int) -> List[Dict[str, Any]]:
    """Parse Bing Images search results."""
    results = []
    
    # Bing uses different selectors
    # Look for image elements in the results
    img_elements = soup.select("img.mimg, .iusc, .imgpt")
    
    for elem in img_elements[:max_results]:
        try:
            # Try to get the full image URL from data attributes
            img_url = elem.get("data-src") or elem.get("src") or elem.get("data-srcset", "").split()[0]
            thumb_url = elem.get("src") or elem.get("data-src")
            
            # Get title/alt text
            title = elem.get("alt") or elem.get("title") or ""
            
            # Get source page link
            parent_link = elem.find_parent("a")
            source_url = parent_link.get("href") if parent_link else ""
            
            if img_url and img_url.startswith("http"):
                results.append({
                    "image_url": img_url,
                    "thumbnail_url": thumb_url or img_url,
                    "title": title,
                    "source_url": source_url,
                    "source_engine": "bing",
                    "width": None,
                    "height": None
                })
        except Exception:
            continue
    
    return results


def parse_duckduckgo_images(soup: BeautifulSoup, max_results: int) -> List[Dict[str, Any]]:
    """Parse DuckDuckGo Images search results."""
    results = []
    
    # DuckDuckGo uses different structure
    img_elements = soup.select(".tile--img__img, .image__img, img.tile--img__img")
    
    for elem in img_elements[:max_results]:
        try:
            img_url = elem.get("data-src") or elem.get("src") or ""
            thumb_url = elem.get("src") or ""
            title = elem.get("alt") or ""
            
            parent_link = elem.find_parent("a", class_="image__link")
            source_url = parent_link.get("href") if parent_link else ""
            
            if img_url and img_url.startswith("http"):
                results.append({
                    "image_url": img_url,
                    "thumbnail_url": thumb_url or img_url,
                    "title": title,
                    "source_url": source_url,
                    "source_engine": "duckduckgo",
                    "width": None,
                    "height": None
                })
        except Exception:
            continue
    
    return results


def parse_google_images(soup: BeautifulSoup, max_results: int) -> List[Dict[str, Any]]:
    """Parse Google Images search results."""
    results = []
    
    # Google Images uses specific structure
    # Look for image containers
    img_containers = soup.select(".rg_i, .isv-r, [data-ri]")
    
    for container in img_containers[:max_results]:
        try:
            # Google often puts data in JSON within the element
            img_elem = container.select_one("img")
            if img_elem:
                img_url = img_elem.get("data-src") or img_elem.get("src") or ""
                thumb_url = img_elem.get("src") or ""
                title = img_elem.get("alt") or ""
                
                parent_link = container.find_parent("a")
                source_url = parent_link.get("href") if parent_link else ""
                
                if img_url and img_url.startswith("http"):
                    results.append({
                        "image_url": img_url,
                        "thumbnail_url": thumb_url or img_url,
                        "title": title,
                        "source_url": source_url,
                        "source_engine": "google",
                        "width": None,
                        "height": None
                    })
        except Exception:
            continue
    
    return results


async def search_images_multi_engine(query: str, engines: List[str] = None, max_results: int = 20) -> List[Dict[str, Any]]:
    """
    Search multiple engines in parallel and merge results.
    Deduplicates by image URL.
    """
    if engines is None:
        engines = ["bing", "duckduckgo"]
    
    tasks = [search_web_images(query, engine, max_results) for engine in engines]
    all_results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Merge and deduplicate
    seen_urls = set()
    merged = []
    
    for engine_results in all_results:
        if isinstance(engine_results, Exception):
            logger.error(f"Search engine error: {engine_results}")
            continue
        for img in engine_results:
            url = img.get("image_url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                merged.append(img)
    
    return merged[:max_results]


async def download_image(url: str, output_path: str) -> bool:
    """
    Download an image from URL and save to disk.
    Returns True on success.
    """
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                from pathlib import Path
                out_path = Path(output_path)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(resp.content)
                return True
    except Exception as e:
        logger.error(f"Failed to download image {url}: {e}")
    return False