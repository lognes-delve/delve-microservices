from typing import Literal, Optional
from ..base import BaseEvent, BaseError
from pydantic import Field

# region Community Events

class CommunityEvent(BaseEvent):
    """Abstraction for any event corresponding to a community"""
    community_id : str

class CommunityCreatedEvent(CommunityEvent):
    """When a community is created"""
    event: Literal["community_created"] = "community_created"

class CommunityModifiedEvent(CommunityEvent):
    """When a community is modified"""
    event : Literal['community_modified'] = 'community_modified'

class CommunityDeletedEvent(CommunityEvent):
    """When a community is deleted"""
    event : Literal['community_deleted'] = 'community_deleted'

# endregion

# region Member Events

class MemberEvent(CommunityEvent):
    """Abstraction for a community event that is related to a user (member)"""
    user_id : str

class JoinedCommunityEvent(MemberEvent):
    """When a user joins a community"""
    event : Literal["joined_community"] = "joined_community"

class LeftCommunityEvent(MemberEvent):
    """When a user leaves a community"""
    event : Literal["left_community"] = "left_community"

    # Whether or not the user left via punishment
    left_by_punishment : bool = Field(default=False)

class MemberModifiedEvent(MemberEvent):
    """When a member is modified"""
    event: Literal["member_modified"] = "member_modified"

# endregion

# region Channel Events

class ChannelEvent(CommunityEvent):
    """Abstraction for events related to channels within a community"""
    channel_id : str

class ChannelCreatedEvent(ChannelEvent):
    event : Literal["channel_created"] = "channel_created"

class ChannelModifiedEvent(ChannelEvent):
    """When a channel is modified (not created)."""
    event : Literal["channel_modified"] = "channel_modified"

class ChannelDeletedEvent(ChannelEvent):
    event : Literal["channel_deleted"] = "channel_deleted"

# endregion