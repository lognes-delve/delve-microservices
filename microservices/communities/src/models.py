from pydantic import BaseModel, Field
from pydantic import computed_field
from typing import Dict, List, Optional, Union
from delve_common._types._dtos._communities._member import Member
from delve_common._types._dtos._user import User
from delve_common.permissions import Permissions
from delve_common._types._dtos._communities._role import Role

class ChannelSpec(BaseModel):

    name : str

class RoleSpec(BaseModel):

    name : str
    colour : Optional[int]
    permission_overrides : Dict[str, bool]

class CommunityTemplate(BaseModel):

    channels : List[ChannelSpec] = Field(default=[])
    roles : List[RoleSpec] = Field(default=[])

class CommunityCreationRequest(BaseModel):

    name : str
    
    template : CommunityTemplate = Field(
        default_factory=lambda: CommunityTemplate())
    
class CommunityEditRequest(BaseModel):
    name : Optional[str] = Field(default=None)
    owner_id : Optional[str] = Field(default=None)

class MemberEditRequest(BaseModel):
    nickname : Optional[str] = Field(default=None)

class MemberWithEmbeddedUser(Member):
    user : User

class ChannelCreationRequest(BaseModel):
    name : str

class ChannelUpdateRequest(BaseModel):
    name : Optional[str] = Field(default=None)

class RolePositionsUpdate(BaseModel):
    role_id : str
    position : int

class FullMember(Member):

    user : User
    roles : List[Role]

    @computed_field
    @property
    def highest_role_id(self) -> Union[str, None]:
        if self.roles:
            return self.roles[0].id

        return None
    
    @computed_field
    @property
    def colour(self) -> Union[int, None]:
        if self.roles:
            return self.roles[0].colour
        
        return None
    
    @computed_field
    @property
    def permissions(self) -> Permissions:
        p = Permissions.default()

        for r in self.roles[::-1]:
            p = p.override(Permissions(**r.permisson_overrides))

        return p
