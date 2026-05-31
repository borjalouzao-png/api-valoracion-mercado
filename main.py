from fastapi import FastAPI
from pydantic import BaseModel
from ddgs import DDGS

app = FastAPI()


class VehicleRequest(BaseModel):
    brand: str
    model: str
    year: int | None = None


@app.get("/")
def home():
    return {"status": "ok"}


@app.post("/market-price")
def market_price(request: VehicleRequest):

    query = f"{request.brand} {request.model}"

    if request.year:
        query += f" {request.year}"

    results = []

    try:

        with DDGS() as ddgs:

            search_results = ddgs.text(
                query + " coches.net autoscout24 wallapop",
                max_results=10
            )

            for item in search_results:

                results.append({
                    "title": item.get("title"),
                    "url": item.get("href"),
                    "snippet": item.get("body")
                })

        return {
            "vehicle": query,
            "results_found": len(results),
            "results": results
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e)
        }
