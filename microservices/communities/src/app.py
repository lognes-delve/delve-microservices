from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from delve_common._types._dtos._communities import Community

from delve_common._db._database import Database, get_client

# Import all of the subrouters
from .subroutes.channels import router as ChannelRouter
from .subroutes.member import router as MemberRouter
from .subroutes.message import router as MessageRouter
from .subroutes.roles import router as RoleRouter

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Database.using_app(app)

# --- COMMUNITY ENDPOINTS
# CREATE A COMMUNITY
# GET A COMMUNITY
# GET LIST OF JOINED COMMUNITIES
# UPDATE A COMMUNITY (METADATA)
# DELETE A COMMUNITY

@app.post("/")
async def create_community() -> Community:
    return # TODO:

@app.get("/list")
async def get_joined_communities() -> List[Community]:
    return # TODO:

@app.get("/{community_id}")
async def get_community() -> Community:
    return # TODO:

@app.patch("/{community_id}")
async def update_community() -> Community:
    return # TODO:

@app.delete("/{community_id}")
async def delete_community() -> None:
    return # TODO:

# ------------------------------------------------
# Below just includes all of the subrouters

app.include_router(ChannelRouter)
app.include_router(MessageRouter)
app.include_router(RoleRouter)
app.include_router(MemberRouter)