from fastapi import FastAPI
from starlette.responses import JSONResponse

app = FastAPI()

@app.get("/")
async def test_endpoint() -> JSONResponse:
    return JSONResponse(
        {"ok" : 1}
    )

