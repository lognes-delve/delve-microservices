from datetime import UTC, datetime
from delve_common._types._dtos._communities._member import Member
from typing import Annotated, List, Optional
from fastapi import Body, Depends, FastAPI
from fastapi.routing import APIRouter
from bson import ObjectId
from pymongo import ReturnDocument
from copy import copy

from delve_common._db._database import get_database
from delve_common._db._redis import get_redis
from delve_common.exceptions import DelveHTTPException
from delve_common._types._dtos._communities import Community
from delve_common._types._dtos._communities._member import Member
from delve_common._types._dtos._communities._role import Role
from ..utils import get_full_member, MemberNotFound

from ..models import FullMember, MemberEditRequest, MemberWithEmbeddedUser
from delve_common._messages.communities import (
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

    comm = await db.get_collection("communities").find_one({'_id' : ObjectId(community_id)})

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

    # Update the edited at timestamp
    diff["edited_at"] = datetime.now(tz=UTC)

    # If nickname is a zero-length string, then unset nickname
    if "nickname" in diff and diff["nickname"] == "":
        diff["nickname"] = None

    before_resp = await db.get_collection("members").find_one_and_update(
        {"user_id" : ObjectId(user_id), "community_id" : ObjectId(community_id)},
        {"$set" : diff},
        return_document=ReturnDocument.BEFORE
    )

    if not before_resp:
        raise DelveHTTPException(
            status_code=404,
            detail="Failed to find member",
            identifier="member_not_found"
        )
    
    before_member = Member(**objectid_fix(before_resp, desired_outcome="str"))

    # Create a copy and apply the new changes
    after_member = copy(before_member)

    for k, v in diff.items():
        setattr(after_member, k, v) # Horrible hack to do this
    
    await redis.publish(
        f"member_modified.{community_id}.{user_id}",
        dump_basemodel_to_json_bytes(
            MemberModifiedEvent(
                community_id=community_id,
                user_id=user_id,
                before = before_member,
                after = after_member
            )
        )
    )

    return after_member

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
) -> FullMember:

    try:
        member = await get_full_member(
            community_id=community_id,
            user_id=user_id
        )
    except MemberNotFound:
        raise DelveHTTPException(
            status_code=404,
            detail="Failed to find member",
            identifier="member_not_found"
        )

    return member

# FIXME: This endpoint is not properly secure, any user can look up a member of any community regardless of whether or not they are part of said community
# FIXME: This endpoint will require pagination for better use in the future probably
# FIXME: This endpoint does not check for the existence of a community
@router.get("/{community_id}/members")
async def get_member_list(
    auth_user_id : Annotated[str, Depends(X_USER_HEADER)],
    community_id : str,
) -> List[FullMember]:

    db = await get_database()

    pipeline = db.get_collection("members").aggregate([
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
        },
        {
            "$lookup" : {
                "from" : "communities",
                "let" : {
                    "user_role_ids" : "$role_ids"
                },
                "pipeline" : [
                    {"$unwind" : "$roles"},
                    {
                        "$match" : {
                            "$expr" : {"$in" : ["$roles.id", "$$user_role_ids"]}
                        }
                    },
                    {
                        "$project" : {
                            "_id" : 0,
                            "roles" : "$roles"
                        }
                    }
                ],
                "as" : "roles"
            }
        },
        {
            "$addFields" : { # flattens the nested group stuff
                "roles" : {
                    "$map" : {
                        "input" : "$roles",
                        "as" : "g",
                        "in" : "$$g.group"
                    }
                }
            }
        }
    ])

    

    return [FullMember(
        **objectid_fix({
            "user" : u["found_user_records"][0],
            "roles" : [Role(**objectid_fix(**ur, desired_outcome="str")) for ur in u['roles']],
            **u
        }, desired_outcome="str")
    ) async for u in pipeline]

__all__ = [router]