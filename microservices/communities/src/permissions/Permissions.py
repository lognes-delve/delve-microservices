from typing import Annotated, Literal, Optional, Self, get_type_hints
from pydantic import BaseModel

class PermissionScope(object):
    scope : str

class GuildPermission(PermissionScope):
    scope = "guild"

class ChannelPermission(PermissionScope):
    scope = "channel"

class Permissions(BaseModel):

    # Guild level permissions
    manage_guild : Annotated[Optional[bool], GuildPermission()] = None

    # TODO<moderation>: These currently are unused
    kick_members : Annotated[Optional[bool], GuildPermission()] = None
    ban_members : Annotated[Optional[bool], GuildPermission()] = None

    # Channel level permissions
    send_messages : Annotated[Optional[bool], ChannelPermission()] = None
    read_messages : Annotated[Optional[bool], ChannelPermission()] = None
    manage_channels : Annotated[Optional[bool], ChannelPermission()] = None
    manage_messages : Annotated[Optional[bool], ChannelPermission()] = None

    @property
    def is_fully_defined(self) -> bool:
        """Returns true if all permissions are set within this object (e.g., no perm is null)"""
        return None not in self.model_dump().values()
    
    @classmethod
    def default(cls) -> "Permissions":
        """Returns the default permissions object"""
        return cls(
            manage_guild = False,
            kick_members = False,
            ban_members = False,

            send_messages=True,
            read_messages=True,
            manage_channels=False,
            manage_messages=False
        )
    
    def override(self : Self, other : "Permissions") -> "Permissions":
        """Returns the current object's permissions overriden by another's"""
        s_model = self.model_dump()
        o_model = other.model_dump(exclude_none=True)
        
        for k, v in o_model.items():
            s_model[k] = v

        return Permissions(**s_model)

    def fill_defaults(self) -> None:
        """Fills the current object's empty permission values with the default ones"""
        defaults = Permissions.default()

        for k, v in defaults.model_dump():
            if getattr(self, k) is None:
                setattr(self, k, v)    

    def get_key_or_default(self, key : str) -> bool:
        """Returns the value set for the permission key, if unset, returns the default value instead"""

        value = getattr(self, key)

        if value is None:
            return getattr(Permissions.default(), key)
        
        return value
    
    def get_key_scope(self, k : str) -> Literal["guild", "channel"]:
        """Returns a literal representing what scope a key is set to. Raises key error if not a valid permission key""" 
        
        type_hints = get_type_hints(self, include_extras=True)[k]

        metadata = type_hints.__metadata__

        if len(metadata) != 1:
            raise Exception("Incorrect number of scopes in metadata (requires only 1)")

        scope_obj = list(metadata)[0]

        if isinstance(scope_obj, GuildPermission):
            return "guild"
        elif isinstance(scope_obj, ChannelPermission):
            return "channel"
        
        raise ValueError(f"Improper permission scope set on key {k}, got {type(scope_obj)}")