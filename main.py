from fastapi import FastAPI
from pydantic import BaseModel
from ddgs import DDGS
import re
from statistics import mean

app = FastAPI()


class VehicleRequest(BaseModel):
    brand: str
    model: str
    year: int | None = None


ALLOWED_DOMAINS = [
    "coches.net",
    "autoscout24.es",
    "autocasion.com",
    "wallapop.com",
    "milanuncios.com"
]

BLOCKED_DOMAINS = [
    "wikipedia.org",
    "youtube.com",
    "tiktok.com",
    "facebook.com",
    "instagram.com",
    "mercedes-benz.com",
    "bmw.es",
    "audi.es"
]


def extract_price(text: str):
    if not text:
        return None

    text = text.replace(".", "").replace(",", "")

    patterns = [
        r"(\d{4,6})\s*€",
        r"€\s*(\d{4,6})",
        r"(\d{4,6})\s*EUR",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            price = int(match.group(1))
            if 3000 <= price <= 200000:
                return price

    return None


def is_allowed_result(url: str):
    if not url:
        return False

    url_lower = url.lower()

    if any(domain in url_lower for domain in BLOCKED_DOMAINS):
        return False

    return any(domain in url_lower for domain in ALLOWED_DOMAINS)


def clean_outliers(prices):
    if len(prices) < 3:
        return prices

    avg = mean(prices)
    cleaned = []

    for price in prices:
        deviation = abs(price - avg) / avg
        if deviation <= 0.25:
            cleaned.append(price)

    return cleaned if cleaned else prices


def confidence_level(count):
    if count >= 6:
        return "alta"
    if count >= 3:
        return "media"
    if count >= 1:
        return "baja"
    return "sin_datos"


def search_market(query: str, market: str):
    results = []
    prices = []

    if market == "canarias":
        search_query = (
            f'{query} Canarias Tenerife Gran Canaria Las Palmas '
            f'site:coches.net OR site:wallapop.com OR site:autoscout24.es OR site:autocasion.com'
        )
    else:
        search_query = (
            f'{query} España Península '
            f'site:coches.net OR site:wallapop.com OR site:autoscout24.es OR site:autocasion.com'
        )

    with DDGS() as ddgs:
        search_results = ddgs.text(
            search_query,
            max_results=20
        )

        for item in search_results:
            title = item.get("title") or ""
            url = item.get("href") or ""
            snippet = item.get("body") or ""

            combined_text = f"{title} {snippet}"

            if not is_allowed_result(url):
                continue

            price = extract_price(combined_text)

            result = {
                "title": title,
                "url": url,
                "snippet": snippet,
                "price_detected": price
            }

            results.append(result)

            if price:
                prices.append(price)

    cleaned_prices = clean_outliers(prices)

    return {
        "market": market,
        "search_query": search_query,
        "results_found": len(results),
        "prices_detected": prices,
        "prices_used": cleaned_prices,
        "average_price": round(mean(cleaned_prices), 2) if cleaned_prices else None,
        "confidence": confidence_level(len(cleaned_prices)),
        "results": results
    }


@app.get("/")
def home():
    return {"status": "ok"}


@app.post("/market-price")
def market_price(request: VehicleRequest):

    vehicle = f"{request.brand} {request.model}"

    if request.year:
        vehicle += f" {request.year}"

    try:
        canary_market = search_market(vehicle, "canarias")
        mainland_market = search_market(vehicle, "peninsula")

        return {
            "vehicle": vehicle,
            "canary_market": canary_market,
            "mainland_market": mainland_market,
            "warning": (
                "Resultados obtenidos mediante búsqueda web gratuita. "
                "La fiabilidad depende de que los portales muestren precios en los snippets."
            )
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
