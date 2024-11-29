
from bson import ObjectId
from delve_common._types._dtos._communities._role import Role
from fastapi import Body, Depends, Query
from fastapi.routing import APIRouter
from typing import Annotated, List
from pymongo import ReturnDocument

from delve_common._db._database import get_database
from delve_common._types._dtos._communities._community import Community
from delve_common._db._redis import get_redis
from delve_common.exceptions import DelveHTTPException

from delve_common._messages.communities import (
    RoleCreatedEvent,
    RoleModifiedEvent,
    RoleDeletedEvent,
    RolePositionsModified
)

from ..models import RolePositionsUpdate, RoleSpec

from ..utils import (dump_basemodel_to_json_bytes, objectid_fix, get_full_member)
from ..constants import X_USER_HEADER

# --- ROLE ENDPOINTS
# CREATE A ROLE
# RETURN A ROLE
# UPDATE A ROLE
# UPDATE ROLE POSITIONS
# DELETE A ROLE
# RETURN THE ROLE LIST (FROM A COMMUNITY) 

router = APIRouter()

@router.post("/{community_id}/roles")
async def create_role(
    x_user : Annotated[str, Depends(X_USER_HEADER)],
    community_id : str,
    rolespec : RoleSpec = Body(),
) -> Role:
    
    db = await get_database()
    redis = await get_redis()

    resp = await db.get_collection("communities").find_one(
        {"_id" : ObjectId(community_id)}
    )

    comm = Community(**objectid_fix(resp, desired_outcome="str"))
    member = await get_full_member(x_user, community_id)

    if comm.owner_id != x_user and member.permissions.manage_community is not True:
        return DelveHTTPException(
            status_code=403,
            detail="Lacking Permissions (requires manage_community)",
            identifier="lacking_permissions"
        )
    
    role = Role(
        id=str(ObjectId()),
        **rolespec.model_dump()
    )

    resp = await db.get_collection("communities").update_one(
        {"_id" : ObjectId(comm.id)},
        {
            "$push" : {
                "roles" : objectid_fix(role.model_dump(), desired_outcome="oid")
            }
        }
    )

    if resp.matched_count < 1:
        raise DelveHTTPException(
            status_code=404,
            detail="Failed to find community?",
            identifier="community_not_found"
        )
    
    # This shouldn't happen
    if resp.modified_count < 1:
        raise DelveHTTPException(
            status_code=500,
            detail="Failed to create role",
            identifier="nightmare_error"
        )
    
    redis.publish(
        f"role_created.{str(community_id)}.{str(role.id)}",
        dump_basemodel_to_json_bytes(
            RoleCreatedEvent(
                community_id=community_id,
                role_id=str(role.id),
                role=role
            )
        )
    )

    # If all goes well, return the new role
    return role



@router.get("/{community_id}/roles")
async def get_role_list(
    x_user : Annotated[str, Depends(X_USER_HEADER)],
    community_id : str
) -> List[Role]:
    
    db = await get_database()

    resp = await db.get_collection("communities").find_one(
        {"_id" : ObjectId(community_id)}
    )

    comm = Community.model_validate(objectid_fix(resp, desired_outcome="str"))

    return comm.roles


@router.get("/{community_id}/roles/{role_id}")
async def get_role(
    x_user : Annotated[str, Depends(X_USER_HEADER)],
    community_id : str,
    role_id : str
) -> Role:

    db = await get_database()

    resp = await db.get_collection("communities").find_one(
        {"_id" : ObjectId(community_id)}
    )

    comm = Community.model_validate(objectid_fix(resp, desired_outcome="str"))

    filtered_roles = [i for i in comm.roles if i.id == role_id]

    if not filtered_roles:
        raise DelveHTTPException(
            status_code=404,
            detail="Failed to find role",
            identifier="role_not_found"
        )

    return filtered_roles[0]

@router.patch("/{community_id}/roles")
async def update_role_positions(
    x_user : Annotated[str, Depends(X_USER_HEADER)],
    community_id : str,
    role_position_update : List[RolePositionsUpdate]
) -> List[Role]:
    
    db = await get_database()
    redis = await get_redis()

    resp = await db.get_collection("communities").find_one(
        {"_id" : ObjectId(community_id)}
    )

    # get all of the roles
    roles_arr : list = resp.get("roles", [])

    role_pos_tuple_pair = {str(r.role_id) : r.position for r in role_position_update}
    
    new_order = sorted(
        roles_arr,
        key = lambda n: (
            roles_arr.index(n) 
            if str(n["_id"]) not in role_pos_tuple_pair 
            else role_pos_tuple_pair[str(n["_id"])]
        )
    )

    await db.get_collection("communities").update_one(
        {"_id" : ObjectId(community_id)},
        {
            "$set" : {
                "roles" : new_order 
            }
        }
    )

    await redis.publish(
        f"role_reorder.{str(community_id)}",
        dump_basemodel_to_json_bytes(
            RolePositionsModified(
                community_id=str(community_id),
                new_order=[Role(**objectid_fix(i, desired_outcome="str")) for i in new_order]
            )
        )
    )

    return new_order

@router.patch("/{community_id}/roles/{role_id}")
async def update_role(
    x_user : Annotated[str, Depends(X_USER_HEADER)],
    community_id : str,
    role_id : str,
    role_spec : RoleSpec = Body()
) -> Role:
    
    db = await get_database()
    redis = await get_redis()

    resp = await db.get_collection("communities").find_one(
        {
            "_id" : ObjectId(community_id),
        }
    )

    lookup = [x for x in resp if x["_id"] == ObjectId(role_id)]

    if not lookup:
        raise DelveHTTPException(
            status_code=404,
            detail="Failed to find role",
            identifier="role_not_found"
        )
    
    role_index = resp.index(lookup[0])
    role = Role(**objectid_fix(**lookup[0], desired_outcome="str"))

    for k, v in role_spec.model_dump(exclude_none=True):
        setattr(role, k, v)

    resp[role_index] = role.model_dump()

    before_doc = await db.get_collection("communities").find_one_and_update(
        {"_id" : ObjectId(community_id)},
        {"roles" : {"$set" : resp}},
        return_document=ReturnDocument.BEFORE
    )

    await redis.publish(
        f"role_updated.{community_id}.{role_id}",
        dump_basemodel_to_json_bytes(
            RoleModifiedEvent(
                community_id=community_id,
                role_id=role_id,
                before=Role(**objectid_fix(before_doc, desired_outcome="str")),
                after=role
            )
        )
    )

    return role

@router.delete("/{community_id}/roles/{role_id}")
async def delete_role(
    x_user : Annotated[str, Depends(X_USER_HEADER)],
    community_id : str,
    role_id : str,
) -> None:
    
    db = await get_database()
    redis = await get_redis()

    resp = await db.get_collection("communities").find_one(
        {
            "_id" : ObjectId(community_id)
        }
    )

    roles = resp.get("roles", [])

    if not resp or not roles:
        raise DelveHTTPException(
            status_code=404,
            identifier="community_not_found",
            detail="Community not found"
        )

    role_index = [i for i, _ in enumerate(roles) if i["_id"] == ObjectId(role_id)][0]

    roles.pop(role_index)

    await db.get_collection("communities").update_one(
        {"_id" : ObjectId(community_id)},
        {"roles" : {"$set" : roles}}
    )

    redis.publish(
        f"role_deleted.{community_id}.{role_id}",
        dump_basemodel_to_json_bytes(
            RoleDeletedEvent(
                community_id=community_id,
                role_id=role_id
            )
        )
    )

    return




__all__ = [router]