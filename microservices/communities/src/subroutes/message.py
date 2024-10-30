
from delve_common._types._dtos._message import Message, MessageContent
from fastapi.routing import APIRouter
from typing import List

# --- MESSAGE ENDPOINTS (MAY REQUIRE SOME GATEWAY INTEGRATION)
# --- gateway will need a pub/sub message broker (FUCK YOU DISTRIBUTED REDIS.)
# CREATE A MESSAGE
# FETCH A SINGLE MESSAGE
# RETURN MANY MESSAGES
# DELETE A MESSAGE
# UPDATE A MESSAGE
# SEMANTIC MESSAGE SEARCH

router = APIRouter()

@router.post("/{community_id}/channels/{channel_id}/messages")
async def create_new_message() -> Message:
    return # TODO:

@router.get("/{community_id}/channels/{channel_id}/messages")
async def get_channel_messages() -> List[Message]:
    return # TODO:

# TODO: Doing this later as it is not imperative to be finished right away
@router.get("/{community_id}/channels/{channel_id}/messages/search")
async def message_search() -> List[Message]:
    return # TODO:

@router.get("/{community_id}/channels/{channel_id}/messages/{message_id}")
async def get_message_by_id() -> Message:
    return # TODO:

@router.delete("/{community_id}/channels/{channel_id}/messages/{message_id}")
async def delete_message() -> None:
    return # TODO:

@router.patch("/{community_id}/channels/{channel_id}/messages/{message_id}")
async def edit_message() -> Message:
    return # TODO:

__all__ = [router]