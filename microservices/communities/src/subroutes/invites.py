from datetime import UTC, datetime, timedelta
import random
import string
import pytz
from bson import ObjectId
from fastapi import APIRouter, Depends, Query
from typing import Annotated, List, Optional

from ..constants import X_USER_HEADER
from ..utils import objectid_fix, dump_basemodel_to_json_bytes
from delve_common._types._dtos._communities._invite import Invite
from delve_common._types._dtos._communities._member import Member
from delve_common._messages.communities import JoinedCommunityEvent

from delve_common._db._database import get_database
from delve_common._db._redis import get_redis
from delve_common.exceptions import DelveHTTPException

router = APIRouter()

async def check_if_invite_code_free(invite_code : str):

    db = await get_database()

    resp = await db.get_collection("invites").find_one({
        "invite_code" : invite_code
    })

    return resp is None

def generate_invite_code(length : int = 6) -> str:
    return "".join(
        random.choices(
            string.ascii_letters,
            k = length
        )
    )

# CREATE AN INVITE
@router.post('/{community_id}/invites')
async def create_invite_code(
    x_user : Annotated[str, Depends(X_USER_HEADER)],
    community_id : str,
    valid_days : int | None = Query(default=None, gt=0, lte=30, )
) -> Invite:    

    db = await get_database()

    community = await db.get_collection("communities").find_one({"_id" : ObjectId(community_id)})

    if not community:
        raise DelveHTTPException(
            status_code=404,
            detail="Failed to find community",
            identifier="community_not_found",
            additional_metadata={
                "community_id" : community_id
            }
        )
    
    iter_count = 0
    failed_codes = []
    while True:
        iter_count += 1 # Safety to avoid an infinite loop

        invite_code = generate_invite_code()
        is_code_free_check = await check_if_invite_code_free(invite_code)

        if is_code_free_check:
            break

        failed_codes.append(invite_code)

        if iter_count >= 3:
            raise DelveHTTPException(
                status_code=409, # Conflict
                detail="Failed to find a free invite code",
                identifier="no_free_codes",
                additional_metadata={
                    "failed_codes" : failed_codes
                }
            )
        
    invite = Invite(
        id = str(ObjectId()),
        community_id=community_id,
        valid_days = valid_days,
        author_id=x_user,
        invite_code=invite_code
    )

    resp = await db.get_collection("invites").insert_one(
        objectid_fix(invite.model_dump(), desired_outcome="oid")
    )

    if not resp:
        raise DelveHTTPException(
            status_code=500,
            detail="Failed to create invite, something went very wrong!",
            identifier="nightmare_error"
        )

    # TODO<redis/polish>: Add an event for this, it's not *really* necessary though

    return invite

# RETRIEVE A LIST OF INVITES FOR A COMMUNITY
@router.get('/{community_id}/invites')
async def get_community_invites(
    x_user : Annotated[str, Depends(X_USER_HEADER)],
    community_id : str
) -> List[Invite]:

    db = await get_database()

    check_for_user = await db.get_collection("members").find_one({
        "user_id" : ObjectId(x_user)
    })

    if not check_for_user:
        raise DelveHTTPException(
            status_code=401,
            detail="You do not have the permissions to access this resource",
            identifier="lacking_permissions"
        )

    cur = db.get_collection("invites").find({
        "community_id" : ObjectId(community_id)
    })

    return [
        Invite(**objectid_fix(inv, desired_outcome="str")) async for inv in cur
    ]

# RETRIEVE AN INVITE
@router.get('/{community_id}/invites/{invite_code}')
async def get_invite_by_code(
    x_user : Annotated[str, Depends(X_USER_HEADER)],
    community_id : str,
    invite_code : str
) -> Invite:

    db = await get_database()

    check_for_user = await db.get_collection("members").find_one({
        "user_id" : ObjectId(x_user)
    })

    if not check_for_user:
        raise DelveHTTPException(
            status_code=401,
            detail="You do not have the permissions to access this resource",
            identifier="lacking_permissions"
        )

    invite = await db.get_collection("invites").find_one({
        "invite_code" : invite_code,
        "community_id" : ObjectId(community_id)
    })

    if not invite:
        raise DelveHTTPException(
            status_code=404,
            detail="Invite not found",
            identifier="invite_not_found"
        )

    return Invite(**objectid_fix(invite, desired_outcome="str"))

# DELETE AN INVITE
@router.delete("/{community_id}/invites/{invite_code}")
async def delete_invite_by_code(
    x_user : Annotated[str, Depends(X_USER_HEADER)],
    community_id : str,
    invite_code : str
) -> None:
    
    db = await get_database()

    resp = await db.get_collection('invites').delete_one({
        "community_id" : ObjectId(community_id),
        "author_id" : ObjectId(x_user),
        "invite_code" : invite_code
    })

    if not resp.deleted_count:
        raise DelveHTTPException(
            status_code=404,
            detail="Invite not found",
            identifier="invite_not_found"
        )

    return

# USE AN INVITE
@router.post("/invite/{invite_code}")
async def use_invite_code(
    x_user : Annotated[str, Depends(X_USER_HEADER)],
    invite_code : str
) -> Member:

    db = await get_database()
    redis = await get_redis()

    await db.get_collection("members").create_index(
        {"user_id" : 1, "community_id" : 1}, 
        unique=True, 
        name="members_composite_index"
    )

    invite = await db.get_collection("invites").find_one(
        {"invite_code" : invite_code}
    )

    if not invite:
        raise DelveHTTPException(
            status_code=404,
            identifier="community_not_found",
            detail="Failed to find community"
        )

    resp = await db.get_collection("members").find_one(
        {"user_id" : ObjectId(x_user), "community_id" : ObjectId(invite["community_id"])}
    )

    if resp:
        raise DelveHTTPException(
            status_code=400,
            identifier="already_joined_community",
            detail="You are already a member of this community!"
        )
    
    invite = Invite(**objectid_fix(invite, desired_outcome="str"))

    if invite.valid_days is not None and pytz.utc.localize(invite.created_at + timedelta(days=invite.valid_days)) < datetime.now(tz=UTC):
        raise DelveHTTPException(
            status_code=410,
            detail="Invite code is expired",
            identifier="invite_code_expired"
        )
    
    new_member = Member(
        id=str(ObjectId()),
        community_id=str(ObjectId(invite.community_id)),
        user_id=str(ObjectId(x_user))
    )

    resp = await db.get_collection("members").insert_one(
        objectid_fix(new_member.model_dump(), desired_outcome="oid")
    )

    await redis.publish(
        f"member_joined.{str(invite.community_id)}.{x_user}",
        dump_basemodel_to_json_bytes(
            JoinedCommunityEvent(
                community_id=str(invite.community_id),
                user_id=x_user,
                member=new_member
            )
        )
    )

    return new_member


__all__ = [router]