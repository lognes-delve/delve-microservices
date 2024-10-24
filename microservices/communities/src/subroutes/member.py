
from delve_common._types._dtos._communities._member import Member
from typing import List
from fastapi.routing import APIRouter

# --- MEMBER ENDPOINTS
# CREATE A MEMBER (MEMBER JOIN)
# DELETE A MEMBER (MEMBER LEAVE)
# UPDATE A MEMBER
# RETURN A SINGLE MEMBER (+ USER INFO)
# RETURN A LIST OF MEMBERS (FROM A COMMUNITY)
# SEMANTIC MEMBER SEARCH (USERNAME / NICKNAME (xor) DISPLAY_NAME)
#   - Nickname overrides display name

router = APIRouter()

@router.post("/{community_id}/members/{user_id}")
async def member_join_community() -> Member:
    return # TODO:

@router.delete("/{community_id}/members/{user_id}")
async def member_leave_community() -> None:
    return # TODO:

@router.patch("/{community_id}/members/{user_id}")
async def update_member() -> Member:
    return # TODO:

@router.get("/{community_id}/members/search")
async def members_semantic_search() -> List[Member]:
    return # TODO:

@router.get("/{community_id}/members/{user_id}")
async def get_member_by_id() -> Member:
    return # TODO:

@router.get("/{community_id}/members")
async def get_member_list() -> List[Member]:
    return # TODO:

__all__ = [router]