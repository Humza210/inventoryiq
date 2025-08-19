import requests
from urllib.parse import quote_plus
from typing import Optional
import os

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
OPENVERSE_ENDPOINT = "https://api.openverse.engineering/v1/images/"

def _serpapi_image(query: str) -> Optional[str]:
    if not SERPAPI_KEY or not query.strip():
        return None
    try:
        r = requests.get(
            "https://serpapi.com/search.json",
            params={"engine": "google_images", "q": query, "ijn": "0",
                    "api_key": SERPAPI_KEY, "safe": "active"},
            timeout=8,
        )
        if r.ok:
            for it in (r.json().get("images_results") or []):
                url = (it.get("original") or it.get("thumbnail") or "").strip()
                if url.startswith("http"):
                    return url
    except Exception:
        pass
    return None

def _openverse_image(query: str) -> Optional[str]:
    try:
        r = requests.get(
            OPENVERSE_ENDPOINT,
            params={"q": query, "page_size": 10, "license": "cc0,cc-by,cc-by-sa", "mature": "false"},
            timeout=6,
        )
        if r.ok:
            for item in r.json().get("results", []):
                url = (item.get("url") or "").strip()
                thumb = (item.get("thumbnail") or "").strip()
                if any(url.lower().endswith(ext) for ext in (".jpg",".jpeg",".png",".webp")):
                    return url
                if thumb:
                    return thumb
    except Exception:
        pass
    return None

def _wikipedia_image(query: str) -> Optional[str]:
    try:
        r = requests.get("https://en.wikipedia.org/w/api.php", params={
            "action": "query", "format": "json", "prop": "pageimages",
            "piprop": "original|thumbnail", "pithumbsize": 800, "titles": query, "redirects": 1
        }, timeout=6)
        if r.ok:
            pages = (r.json().get("query", {}).get("pages", {}) or {})
            for _, page in pages.items():
                img = page.get("original", {}).get("source") or page.get("thumbnail", {}).get("source")
                if img:
                    return img
    except Exception:
        pass
    return None

def best_image_for_name(name: str) -> str:
    q = (name or "").strip()
    if not q:
        return "https://picsum.photos/seed/placeholder/600/400"
    for fn in (_serpapi_image, _openverse_image, _wikipedia_image):
        url = fn(q)
        if url:
            return url
    return f"https://source.unsplash.com/600x400/?{quote_plus(q)}"
