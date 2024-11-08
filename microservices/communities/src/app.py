from fastapi import Depends, FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from typing import Annotated, List
from datetime import datetime, UTC
from bson import ObjectId
from pymongo import ReturnDocument

from delve_common._db._database import Database, get_database
from delve_common._db._redis import get_redis, DelveRedis
from delve_common.exceptions import DelveHTTPException

from .constants import X_USER_HEADER
from .models import CommunityCreationRequest, CommunityEditRequest
from .utils import dump_basemodel_to_json_bytes, objectid_fix

from delve_common._types._dtos._communities import Community
from delve_common._types._dtos._communities._channel import Channel
from delve_common._types._dtos._communities._role import Role

# Import all of the subrouters
from .subroutes.channels import router as ChannelRouter
from .subroutes.member import router as MemberRouter
from .subroutes.message import router as MessageRouter
from .subroutes.roles import router as RoleRouter

from .messaging.messages.out.communities import (
    CommunityCreatedEvent,
    CommunityModifiedEvent,
    CommunityDeletedEvent
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Database.using_app(app)
DelveRedis.using_app(app)

@app.post("/")
async def create_community(
    user_id : Annotated[str, Depends(X_USER_HEADER)],
    creationReq : CommunityCreationRequest
) -> Community:
    
    db = await get_database()
    redis = await get_redis()

    # Store the community id for nested list comprehensions
    comm_id = ObjectId()

    # Build that big community object
    comm = Community(
        id = str(comm_id),
        name = creationReq.name,
        owner_id = str(user_id),
        channel_ids = [],
        role_ids = [],
    )

    resp = await db.get_collection("communities").insert_one(
        objectid_fix(comm.model_dump(), desired_outcome="oid")
    )

    # If the response from the database is not an acknowledged write, raise an error
    if not resp.acknowledged:
        raise DelveHTTPException(
            status_code=500,
            detail="Failed to create community",
            identifier="failed_to_create_community",
            additional_metadata={
                "user_id" : user_id,
                "community_dump" : comm.model_dump()
            }
        )
    
    created_template_channels : List[ObjectId] = []
    created_template_roles : List[ObjectId] = []
    
    if creationReq.template.channels:

        resp = await db.get_collection("channels").insert_many(
            [
                objectid_fix(Channel(
                    id=str(ObjectId()),
                    community_id=str(comm_id),
                    name = chan.name
                ).model_dump(), desired_outcome="oid") 
                for chan in creationReq.template.channels
            ]
        )

        created_template_channels = resp.inserted_ids

    if creationReq.template.roles:

        resp = await db.get_collection("roles").insert_many(
            [
                objectid_fix(Role(
                    id=str(ObjectId()),
                    community_id=str(comm_id),
                    name = role.name,
                    colour = role.colour
                ).model_dump(), desired_outcome="oid")
                for role in creationReq.template.roles
            ]
        )

        created_template_roles = resp.inserted_ids

    comm = await db.get_collection("communities").find_one_and_update(
        {"_id" : comm_id},
        {"$set" : {
            "role_ids" : created_template_roles,
            "channel_ids" : created_template_channels
        }},
        return_document=ReturnDocument.AFTER
    )

    comm = Community(**objectid_fix(comm, desired_outcome="str"))
    
    # Send an event to the gateway signifying that a new community was created
    # This isn't normally broadcasted to users, but may be useful for the future
    # (This is also just the first place redis was implemented anyways, because the integration is so simple)
    await redis.publish(
        f"community_created.{str(comm_id)}",
        dump_basemodel_to_json_bytes(
            CommunityCreatedEvent(community_id=str(comm_id))
        )
    )

    # If all goes well, return the new community
    return comm

@app.get("/list")
async def get_joined_communities(
    user_id : Annotated[str, Depends(X_USER_HEADER)]
) -> List[Community]:
    return # TODO: (Requires members subroutes to be done first)

@app.get("/{community_id}")
async def get_community(
    user_id : Annotated[str, Depends(X_USER_HEADER)],
    community_id : str
) -> Community:
    
    db = await get_database()

    # TODO: Any user can look up any community with this simple find
    res = await db.get_collection("communities").find_one(
        {"_id" : ObjectId(community_id)}
    )

    if not res:
        raise DelveHTTPException(
            status_code=404,
            identifier="community_not_found",
            detail="Failed to find community",
            additional_metadata={"community_id" : community_id}
        )
    
    return Community(**objectid_fix(res, desired_outcome="str"))

@app.patch("/{community_id}")
async def update_community(
    user_id : Annotated[str, Depends(X_USER_HEADER)],
    community_id : str,
    community_update : CommunityEditRequest
) -> Community:
    
    db = await get_database()
    redis = await get_redis()

    # Model dump the basemodel into a dict, returning only things that ARENT `None`
    diff = community_update.model_dump(exclude_none=True)

    if not diff:
        raise DelveHTTPException(
            status_code=400,
            detail="No changes found",
            identifier="no_changes_found"
        )
    
    # Get a reference to the community
    community = await db.get_collection("communities").find_one({"_id" : ObjectId(community_id)})

    # Ensure the community exists
    if not community:
        raise DelveHTTPException(
            status_code=404,
            detail="Failed to find community",
            identifier="community_not_found"
        )
    
    # init an object to ensure everything is okay
    community = Community(**objectid_fix(community, desired_outcome="str"))
    
    # region | # TODO<advanced-perms>: This will need revision when implementing advanced permissions
    if user_id != community.owner_id:
        raise DelveHTTPException(
            status_code=401,
            detail="You don't have permission to do this",
            identifier="lacking_permissions"
        )
    # endregion

    resp = await db.get_collection("communities").find_one_and_update(
        {"_id" : ObjectId(community_id)},
        {"$set" : {
            "edited_at" : datetime.now(tz=UTC), # Update the edited_at field on the community
            **diff # Push the diff into the community
        }},
        return_document=ReturnDocument.AFTER # Return the document after the modification
    )

    # This shouldn't happen.
    if not resp:
        raise DelveHTTPException(
            status_code=500,
            detail="Failed to update community",
            identifier="nightmare_error"
        )

    await redis.publish(
        f"community_modified.{community_id}",
        dump_basemodel_to_json_bytes(
            CommunityModifiedEvent(
                community_id=community_id
            )
        )
    )

    # Return the updated community
    return Community(**objectid_fix(resp, desired_outcome="str"))

@app.delete("/{community_id}")
async def delete_community(
    user_id : Annotated[str, Depends(X_USER_HEADER)],
    community_id : str
) -> None:
    
    db = await get_database()
    redis = await get_redis()

    # Get a reference to the community
    community = await db.get_collection("communities").find_one({"_id" : ObjectId(community_id)})

    # Ensure the community exists
    if not community:
        raise DelveHTTPException(
            status_code=404,
            detail="Failed to find community",
            identifier="community_not_found"
        )
    
    # init an object to ensure everything is okay
    community = Community(**objectid_fix(community, desired_outcome="str"))
    
    # region | # TODO<advanced-perms>: This will need revision when implementing advanced permissions
    if user_id != community.owner_id:
        raise DelveHTTPException(
            status_code=401,
            detail="You don't have permission to do this",
            identifier="lacking_permissions"
        )
    # endregion

    # Delete the community
    resp = await db.get_collection("communities").delete_one({"_id" : ObjectId(community_id)})

    # This shouldn't happen.
    if resp.deleted_count != 1:
        raise DelveHTTPException(
            status_code=500,
            detail="Failed to delete community",
            identifier="nightmare_error"
        )

    # Delete all of the other resources assoc. with the community if the community deletes succesfully
    # NOTE: If a community is deleted, then it is ASSUMED that ALL other resources assoc. with the community
    #       have been deleted as well. I cba to send out all of the other redis events for it.  
    await db.get_collection("community_messages").delete_many({{"community_id" : ObjectId(community_id)}})
    await db.get_collection("channels").delete_many({"community_id" : ObjectId(community_id)})
    await db.get_collection("members").delete_many({"community_id" : ObjectId(community)})
    # TODO: This needs to also delete roles when the time comes to implement them

    await redis.publish(
        f"community_deleted.{community_id}",
        dump_basemodel_to_json_bytes(
            CommunityDeletedEvent(
                community_id=community_id
            )
        )
    )

    return

# ------------------------------------------------
# Below just includes all of the subrouters

app.include_router(ChannelRouter)
app.include_router(MessageRouter)
app.include_router(RoleRouter)
app.include_router(MemberRouter)