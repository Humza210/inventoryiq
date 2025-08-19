import os, re, requests
from typing import Optional

DEFAULT_CITY = os.getenv("DEFAULT_CITY", "Naperville, IL")
DEFAULT_ZIP = os.getenv("DEFAULT_ZIP", "60540")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
KROGER_CLIENT_ID = os.getenv("KROGER_CLIENT_ID")
KROGER_CLIENT_SECRET = os.getenv("KROGER_CLIENT_SECRET")

def _kroger_token() -> Optional[str]:
    if not KROGER_CLIENT_ID or not KROGER_CLIENT_SECRET:
        return None
    try:
        r = requests.post(
            "https://api.kroger.com/v1/connect/oauth2/token",
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
            data={"grant_type": "client_credentials", "scope": "product.compact"},
            auth=(KROGER_CLIENT_ID, KROGER_CLIENT_SECRET),
            timeout=12
        )
        if r.ok:
            return r.json().get("access_token")
    except Exception:
        pass
    return None

def _kroger_nearest_location(token: str, postal_code: str) -> Optional[str]:
    try:
        r = requests.get(
            "https://api.kroger.com/v1/locations",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            params={"filter.zipCode.near": postal_code, "filter.limit": 5},
            timeout=12
        )
        if r.ok:
            for loc in (r.json().get("data") or []):
                loc_id = loc.get("locationId")
                if loc_id:
                    return loc_id
    except Exception:
        pass
    return None

def _kroger_price_cents(token: str, location_id: str, query: str) -> Optional[int]:
    if not query.strip():
        return None
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    base = query.strip()
    variants = [
        base,
        " ".join(base.split()[:2]),
        base.replace("graham", "grahams"),
        base.replace("bunnies", "bunny"),
        base.replace("crackers", "cracker"),
        base.replace("mix", "snack mix"),
        f"Annie's {base}",
        f"Ritz {base}",
    ]
    best = None
    for q in variants:
        if not q:
            continue
        try:
            r = requests.get(
                "https://api.kroger.com/v1/products",
                headers=headers,
                params={"filter.locationId": location_id, "filter.term": q, "filter.limit": 16},
                timeout=12
            )
            if not r.ok:
                continue
            for prod in (r.json().get("data") or []):
                for it in (prod.get("items") or []):
                    price = it.get("price") or {}
                    dollars = price.get("promo", price.get("regular"))
                    if dollars is None:
                        continue
                    try:
                        cents = int(round(float(dollars) * 100))
                    except Exception:
                        continue
                    if cents > 0 and (best is None or cents < best):
                        best = cents
        except Exception:
            continue
        if best is not None:
            break
    return best

def _serpapi_shopping_price_cents(query: str) -> Optional[int]:
    if not SERPAPI_KEY or not query.strip():
        return None
    try:
        r = requests.get(
            "https://serpapi.com/search.json",
            params={"engine": "google_shopping", "q": query, "api_key": SERPAPI_KEY,
                    "gl": "us", "hl": "en", "num": 10},
            timeout=12
        )
        if not r.ok:
            return None
        for item in (r.json().get("shopping_results") or []):
            price_str = (item.get("price") or "").strip()
            if not price_str:
                continue
            m = re.search(r"\$([\d,]+(?:\.\d{1,2})?)", price_str)
            if not m:
                continue
            dollars = float(m.group(1).replace(",", ""))
            cents = int(round(dollars * 100))
            if cents > 0:
                return cents
    except Exception:
        return None
    return None

def local_price_cents(name: str, postal_code: str = DEFAULT_ZIP) -> Optional[int]:
    token = _kroger_token()
    if token:
        loc = _kroger_nearest_location(token, postal_code)
        if loc:
            cents = _kroger_price_cents(token, loc, name)
            if cents is not None:
                return cents
    return _serpapi_shopping_price_cents(f"{name} {DEFAULT_CITY}")
