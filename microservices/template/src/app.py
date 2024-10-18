from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from delve_common._db._database import Database, get_client

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Database.using_app(app)

@app.get("/")
async def test_endpoint() -> JSONResponse:

    db = await get_client() 

    db_resp = await db.admin.command({"ping" : 1})

    return JSONResponse(
        {"ok" : "True", "db" : db_resp}
    )

