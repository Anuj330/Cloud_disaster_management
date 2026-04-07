import os
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="Mock Service")

SERVICE_NAME = os.getenv("MOCK_SERVICE_NAME", "sample-service")
SERVICE_REGION = os.getenv("MOCK_SERVICE_REGION", "region-a")
SERVICE_PORT = int(os.getenv("MOCK_SERVICE_PORT", "9001"))

state = {"failing": False}


@app.get("/health")
def health():
    if state["failing"]:
        return JSONResponse(
            status_code=503,
            content={"status": "down", "service": SERVICE_NAME, "region": SERVICE_REGION, "port": SERVICE_PORT},
        )
    return {"status": "ok", "service": SERVICE_NAME, "region": SERVICE_REGION, "port": SERVICE_PORT}


@app.post("/toggle-failure")
def toggle_failure(failing: bool) -> dict:
    state["failing"] = failing
    return {"service": SERVICE_NAME, "region": SERVICE_REGION, "failing": state["failing"]}
