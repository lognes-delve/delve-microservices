
from delve_common._types._dtos._communities._role import Role
from fastapi.routing import APIRouter
from typing import List

# --- ROLE ENDPOINTS
# CREATE A ROLE
# RETURN A ROLE
# UPDATE A ROLE
# DELETE A ROLE
# RETURN THE ROLE LIST (FROM A COMMUNITY) 

router = APIRouter()

@router.post("/{community_id}/roles")
async def create_role() -> Role:
    return # TODO:

@router.get("/{community_id}/roles")
async def get_role_list() -> List[Role]:
    return # TODO:

@router.get("/{community_id}/roles/{role_id}")
async def get_role() -> Role:
    return # TODO:

@router.patch("/{community_id}/roles/{role_id}")
async def update_role() -> Role:
    return # TODO:

@router.delete("/{community_id}/roles/{role_id}")
async def delete_role() -> None:
    return # TODO:

__all__ = [router]