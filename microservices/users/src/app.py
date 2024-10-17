from fastapi import FastAPI
from starlette.responses import JSONResponse

from delve_common._db._database import Database, get_client

app = FastAPI()

Database.using_app(app)

@app.get("/")
async def test_endpoint() -> JSONResponse:

    db = await get_client() 

    db_resp = await db.admin.command({"ping" : 1})

    return JSONResponse(
        {"ok" : "True", "db" : db_resp, "m" : "users"}
    )

