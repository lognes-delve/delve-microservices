from pydantic import BaseModel, Field
from typing import List, Optional
from delve_common._types._dtos._communities._member import Member
from delve_common._types._dtos._user import User

class ChannelSpec(BaseModel):

    name : str

class RoleSpec(BaseModel):

    name : str
    colour : Optional[int]

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
