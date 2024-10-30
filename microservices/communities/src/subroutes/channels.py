
from datetime import UTC, datetime
from typing import List, Annotated
from fastapi import Depends
from fastapi.routing import APIRouter
from bson import ObjectId
from pymongo import ReturnDocument

from ..constants import X_USER_HEADER
from ..models import (
    ChannelCreationRequest, 
    ChannelUpdateRequest
)
from ..utils import objectid_fix, dump_basemodel_to_json_bytes

from delve_common._types._dtos._communities._channel import Channel
from delve_common._types._dtos._communities._community import Community
from delve_common._db._database import get_database
from delve_common._db._redis import get_redis
from delve_common.exceptions import DelveHTTPException
from ..messaging.messages.out.communities import (
    ChannelCreatedEvent, 
    ChannelDeletedEvent, 
    ChannelModifiedEvent
)

# --- CHANNEL ENDPOINTS
# CREATE A CHANNEL
# GET A SINGLE CHANNEL
# RETURN ALL COMMUNITY CHANNELS
# UPDATE A CHANNEL
# DELETE A CHANNEL

router = APIRouter()

@router.get("/{community_id}/channels")
async def get_all_channels(
    x_user : Annotated[str, Depends(X_USER_HEADER)],
    community_id : str
) -> List[Channel]:
    # NOTE: This doesn't double check to make sure that the community exists,
    # but it'll return nothing at all if the community doesnt exist anyways so
    # it doesn't *technically* matter.
    
    db = await get_database()

    res = db.get_collection("channels").find({"community_id" : ObjectId(community_id)})

    return [
        Channel(**objectid_fix(
            c, desired_outcome="str"
        )) async for c in res 
    ]

@router.post("/{community_id}/channels")
async def create_channel(
    x_user : Annotated[str, Depends(X_USER_HEADER)],
    community_id : str,
    channel_creation_req : ChannelCreationRequest
) -> Channel:
    
    redis = await get_redis()
    db = await get_database()

    community = await db.get_collection("communities").find_one(
        {"_id" : ObjectId(community_id)}
    )

    if not community:
        raise DelveHTTPException(
            status_code=404,
            detail="Failed to find community",
            identifier="community_not_found",
            additional_metadata={
                "community_id" : community_id
            }
        )
    
    community = Community(**objectid_fix(
        community, desired_outcome="str"
    ))
    
    #  TODO<advanced_perms>: This needs to be changed when implementing a proper permissions system
    if x_user != community.owner_id:
        raise DelveHTTPException(
            status_code=403,
            detail="You do not have the permissions to do this",
            identifier="lacking_permissions"
        )

    channel = Channel(
        id = str(ObjectId()),
        community_id=community_id,
        name = channel_creation_req.name
    )

    resp = await db.get_collection("channels").insert_one(
        objectid_fix(channel.model_dump(), desired_outcome="oid")
    )

    if not resp.inserted_id:
        raise DelveHTTPException(
            status_code=500,
            detail="Failed to create channel",
            identifier="failed_to_create_channel"
        )
    
    await redis.publish(
        f"channel_created.{community_id}.{str(channel.id)}",
        dump_basemodel_to_json_bytes(
            ChannelCreatedEvent(
                community_id=community.id,
                channel_id=channel.id
            )
        )
    )

    return channel

@router.get("/{community_id}/channels/{channel_id}")
async def get_channel_by_id(
    x_user : Annotated[str, Depends(X_USER_HEADER)],
    community_id : str,
    channel_id : str
) -> Channel:
    
    db = await get_database()

    res = await db.get_collection("channels").find_one(
        {"community_id" : ObjectId(community_id), "_id" : ObjectId(channel_id)}
    )

    if not res:
        raise DelveHTTPException(
            status_code=404,
            detail="Failed to find channel",
            identifier="failed_to_find_channel"
        )
    
    chan = Channel(**objectid_fix(res, desired_outcome="str"))

    return chan

@router.patch("/{community_id}/channels/{channel_id}")
async def update_channel(
    x_user : Annotated[str, Depends(X_USER_HEADER)],
    community_id : str,
    channel_id : str,
    channel_update_req : ChannelUpdateRequest
) -> Channel:
    
    redis = await get_redis()
    db = await get_database()

    diff = channel_update_req.model_dump(exclude_none=True)

    comm = await db.get_collection("communities").find_one(
        {"_id" : ObjectId(community_id)}
    )

    if not comm:
        raise DelveHTTPException(
            status_code=404,
            detail="Failed to find community",
            identifier="community_not_found"
        )
    
    comm = Community(
        **objectid_fix(comm, desired_outcome="str")
    )

    # TODO<advanced_permissions>: You know what to do
    if comm.owner_id != x_user:
        raise DelveHTTPException(
            status_code=403,
            detail="Lacking permissions",
            identifier="lacking_permissions"
        )
    
    res = await db.get_collection("channels").find_one_and_update(
        {"community_id" : ObjectId(comm.id), "_id" : ObjectId(channel_id)},
        {"$set" : {**diff, "edited_at" : datetime.now(tz=UTC)}},
        return_document=ReturnDocument.AFTER
    )

    if not res:
        raise DelveHTTPException(
            status_code=404,
            detail="Failed to find channel",
            identifier="channel_not_found"
        )
    
    await redis.publish(
        f"channel_modified.{comm.id}.{channel_id}",
        dump_basemodel_to_json_bytes(
            ChannelModifiedEvent(
                community_id=comm.id,
                channel_id=channel_id
            )
        )
    )

    updated_channel = Channel(**objectid_fix(res, desired_outcome="str"))
    
    return updated_channel

@router.delete("/{community_id}/channels/{channel_id}")
async def delete_channel(
    x_user : Annotated[str, Depends(X_USER_HEADER)],
    community_id : str,
    channel_id : str
) -> None:
    
    redis = await get_redis()
    db = await get_database()

    comm = await db.get_collection("communities").find_one(
        {"_id" : ObjectId(community_id)}
    )

    if not comm:
        raise DelveHTTPException(
            status_code=404,
            detail="Community not found",
            identifier="community_not_found"
        )
    
    comm = Community(**objectid_fix(comm, desired_outcome="str"))

    # TODO<advanced_perms>: Yeah.
    if x_user != comm.owner_id:
        raise DelveHTTPException(
            status_code=403,
            detail="Lacking permissions",
            identifier="lacking_permissions"
        )
    
    res = await db.get_collection("channels").delete_one({"_id" : ObjectId(channel_id)})

    if res.deleted_count != 1:
        raise DelveHTTPException(
            status_code=404,
            detail="Failed to find channel",
            identifier="channel_not_found"
        )
    
    await redis.publish(
        f"channel_deleted.{community_id}.{channel_id}",
        dump_basemodel_to_json_bytes(
            ChannelDeletedEvent(
                community_id=community_id,
                channel_id=channel_id
            )
        )
    )

    return

__all__ = [router]