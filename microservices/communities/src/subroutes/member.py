
from contextlib import asynccontextmanager
from delve_common._types._dtos._communities._member import Member
from typing import Annotated, List, Optional
from fastapi import Body, Depends, FastAPI
from fastapi.routing import APIRouter
from bson import ObjectId
from pymongo import ReturnDocument

from delve_common._db._database import get_database
from delve_common._db._redis import get_redis
from delve_common.exceptions import DelveHTTPException
from delve_common._types._dtos._communities import Community
from delve_common._types._dtos._communities._member import Member

from ..models import MemberEditRequest, MemberWithEmbeddedUser
from ..messaging.messages.out.communities import (
    MemberModifiedEvent, JoinedCommunityEvent, LeftCommunityEvent
)

from ..utils import objectid_fix, dump_basemodel_to_json_bytes

from ..constants import X_USER_HEADER

# --- MEMBER ENDPOINTS
# CREATE A MEMBER (MEMBER JOIN)
# DELETE A MEMBER (MEMBER LEAVE)
# UPDATE A MEMBER
# RETURN A SINGLE MEMBER (+ USER INFO)
# RETURN A LIST OF MEMBERS (FROM A COMMUNITY)
# SEMANTIC MEMBER SEARCH (USERNAME / NICKNAME (xor) DISPLAY_NAME)
#   - Nickname overrides display name

router = APIRouter()

@router.post("/{community_id}/members")
async def member_join_community(
    user_id : Annotated[str, Depends(X_USER_HEADER)],
    community_id : str,
) -> Member:
    
    db = await get_database()
    redis = await get_redis()

    await db.get_collection("members").create_index(
        {"user_id" : 1, "community_id" : 1}, 
        unique=True, 
        name="members_composite_index"
    )

    comm = await db.get_collection("communities").find_one({'_id' : ObjectId(community_id)})

    if not comm:
        raise DelveHTTPException(
            status_code=404,
            identifier="community_not_found",
            detail="Failed to find community"
        )

    # Cast to ensure everything is fine, after this point is is assumed that the community must exist
    comm = Community(**objectid_fix(comm, desired_outcome="str"))

    resp = await db.get_collection("members").find_one(
        {"user_id" : ObjectId(user_id), "community_id" : ObjectId(community_id)}
    )

    if resp:
        raise DelveHTTPException(
            status_code=400,
            identifier="already_joined_community",
            detail="You are already a member of this community!"
        )
    
    new_member = Member(
        id=str(ObjectId()),
        community_id=str(ObjectId(community_id)),
        user_id=str(ObjectId(user_id))
    )

    resp = await db.get_collection("members").insert_one(
        objectid_fix(new_member.model_dump(), desired_outcome="oid")
    )

    await redis.publish(
        f"member_joined.{community_id}.{user_id}",
        dump_basemodel_to_json_bytes(
            JoinedCommunityEvent(
                community_id=community_id,
                user_id=user_id
            )
        )
    )

    return new_member

@router.delete("/{community_id}/members")
async def member_leave_community(
    user_id : Annotated[str, Depends(X_USER_HEADER)],
    community_id : str
) -> None:
    
    db = await get_database()
    redis = await get_redis()

    resp = await db.get_collection("members").delete_one(
        {"user_id" : ObjectId(user_id), "community_id" : ObjectId(community_id)}
    )

    if resp.deleted_count != 1:
        raise DelveHTTPException(
            status_code=404,
            detail="Failed to find member",
            identifier="member_not_found",
            additional_metadata={
                "community_id" : community_id,
                "user_id" : user_id
            }
        )
    
    await redis.publish(
        f"member_left.{community_id}.{user_id}",
        dump_basemodel_to_json_bytes(
            LeftCommunityEvent(
                community_id=community_id,
                user_id=user_id,
                left_by_punishment=False
            )
        )
    )
    
    return

@router.patch("/{community_id}/members/{user_id}")
async def update_member(
    auth_user_id : Annotated[str, Depends(X_USER_HEADER)],
    community_id : str,
    user_id : str,
    member_edit_request : MemberEditRequest = Body()
) -> Member:
    
    db = await get_database()
    redis = await get_redis()

    comm = await db.get_collection("communities").find_one({'id' : community_id})

    if not comm:
        raise DelveHTTPException(
            status_code=404,
            identifier="community_not_found",
            detail="Failed to find community"
        )

    # Cast to ensure everything is fine, after this point is is assumed that the community must exist
    comm = Community(**objectid_fix(comm, desired_outcome="str"))

    if auth_user_id != user_id and auth_user_id != comm.owner_id:
        raise DelveHTTPException(
            status_code=403,
            detail="You're not allowed to do this action to this user",
            identifier="lacking-permissions"
        )
    
    diff = member_edit_request.model_dump(exclude_none=True)

    # If nickname is a zero-length string, then unset nickname
    if "nickname" in diff and diff["nickname"] == "":
        diff["nickname"] = None

    resp = await db.get_collection("members").find_one_and_update(
        {"user_id" : ObjectId(user_id), "community_id" : ObjectId(community_id)},
        {"$set" : diff},
        return_document=ReturnDocument.AFTER
    )

    if not resp:
        raise DelveHTTPException(
            status_code=404,
            detail="Failed to find member",
            identifier="member_not_found"
        )
    
    await redis.publish(
        f"member_modified.{community_id}.{user_id}",
        dump_basemodel_to_json_bytes(
            MemberModifiedEvent(
                community_id=community_id,
                user_id=user_id
            )
        )
    )

    return Member(**objectid_fix(resp, desired_outcome="str"))

@router.get("/{community_id}/members/search")
async def members_search() -> List[Member]:
    return # TODO: This isn't a high priority endpoint, will implement when needed

# FIXME: This endpoint is not properly secure, any user can look up a member of any community regardless of whether or not they are part of said community
# FIXME: This endpoint does not check for the existence of a community
@router.get("/{community_id}/members/{user_id}")
async def get_member_by_id(
    auth_user_id : Annotated[str, Depends(X_USER_HEADER)],
    community_id : str,
    user_id : str,
) -> MemberWithEmbeddedUser:

    db = await get_database()

    pipeline = db.get_collection("members").aggregate(
        [
            {
                "$match" : {
                    "user_id" : ObjectId(user_id),
                    "community_id" : ObjectId(community_id)
                }
            },
            {
                "$lookup" : {
                    "from" : "users",
                    "localField" : "user_id",
                    "foreignField" : "_id",
                    "as" : "user"
                }
            }
        ]
    )

    resp = [x async for x in pipeline]

    if not resp:
        raise DelveHTTPException(
            status_code=404,
            detail="Failed to find member",
            identifier="member_not_found"
        )
    
    user_ref = resp[0]["user"][0]
    del resp[0]["user"]

    return MemberWithEmbeddedUser(
        **objectid_fix({"user" : user_ref, **resp[0]}, desired_outcome="str")
    )

# FIXME: This endpoint is not properly secure, any user can look up a member of any community regardless of whether or not they are part of said community
# FIXME: This endpoint will require pagination for better use in the future probably
# FIXME: This endpoint does not check for the existence of a community
@router.get("/{community_id}/members")
async def get_member_list(
    auth_user_id : Annotated[str, Depends(X_USER_HEADER)],
    community_id : str,
) -> List[MemberWithEmbeddedUser]:

    db = await get_database()

    pipeline = db.get_collection("members").aggregate(
        [
            {
                "$match" : {
                    "community_id" : ObjectId(community_id)
                }
            },
            {
                "$lookup" : {
                    "from" : "users",
                    "localField" : "user_id",
                    "foreignField" : "_id",
                    "as" : "found_user_records"
                }
            }
        ]
    )

    return [MemberWithEmbeddedUser(
        **objectid_fix({"user" : u['found_user_records'][0], **u}, desired_outcome="str")
    ) async for u in pipeline]

__all__ = [router]