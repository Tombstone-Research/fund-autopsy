"""FastAPI backend for Fund Autopsy web UI."""

from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(
    title="Fund Autopsy",
    description="Mutual fund total cost of ownership analyzer",
    version="0.1.0",
)


@app.get("/")
async def root():
    return {"name": "Fund Autopsy", "version": "0.1.0", "by": "Tombstone Research"}


# TODO: Implement API endpoints
# GET /api/fund/{ticker} — Single fund analysis
# GET /api/compare?tickers=AGTHX,VFIAX — Comparison mode
# GET /api/fund/{ticker}/history — Time series
