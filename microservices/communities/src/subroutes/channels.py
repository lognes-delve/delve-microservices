
from typing import List
from fastapi.routing import APIRouter
from delve_common._types._dtos._communities._channel import Channel

# --- CHANNEL ENDPOINTS
# CREATE A CHANNEL
# GET A SINGLE CHANNEL
# RETURN ALL COMMUNITY CHANNELS
# UPDATE A CHANNEL
# DELETE A CHANNEL

router = APIRouter()

@router.get("/{community_id}/channels")
async def get_all_channels() -> List[Channel]:
    return # TODO:

@router.post("/{community_id}/channels")
async def create_channel() -> Channel:
    return # TODO:

@router.get("/{community_id}/channels/{channel_id}")
async def get_channel_by_id() -> Channel:
    return # TODO:

@router.patch("/{community_id}/channels/{channel_id}")
async def update_channel() -> Channel:
    return # TODO:

@router.delete("/{community_id}/channels/{channel_id}")
async def delete_channel() -> None:
    return # TODO:

__all__ = [router]