from typing import Literal, Optional
from ..base import BaseEvent, BaseError
from pydantic import Field

from delve_common._types._dtos._message import Message
from delve_common._types._dtos._communities._community import Community
from delve_common._types._dtos._communities._member import Member
from delve_common._types._dtos._communities._channel import Channel

# region Community Events

class CommunityEvent(BaseEvent):
    """Abstraction for any event corresponding to a community"""
    community_id : str

class CommunityCreatedEvent(CommunityEvent):
    """When a community is created"""
    event: Literal["community_created"] = "community_created"
    community : Community

class CommunityModifiedEvent(CommunityEvent):
    """When a community is modified"""
    event : Literal['community_modified'] = 'community_modified'
    before : Community
    after : Community

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
    member : Member

class LeftCommunityEvent(MemberEvent):
    """When a user leaves a community"""
    event : Literal["left_community"] = "left_community"

    # Whether or not the user left via punishment
    left_by_punishment : bool = Field(default=False)

class MemberModifiedEvent(MemberEvent):
    """When a member is modified"""
    event: Literal["member_modified"] = "member_modified"

    before : Member
    after : Member

# endregion

# region Channel Events

class ChannelEvent(CommunityEvent):
    """Abstraction for events related to channels within a community"""
    channel_id : str

class ChannelCreatedEvent(ChannelEvent):
    event : Literal["channel_created"] = "channel_created"

    channel : Channel

class ChannelModifiedEvent(ChannelEvent):
    """When a channel is modified (not created)."""
    event : Literal["channel_modified"] = "channel_modified"

    before : Channel
    after : Channel

class ChannelDeletedEvent(ChannelEvent):
    event : Literal["channel_deleted"] = "channel_deleted"

# endregion

# region Message Events

class CommunityMessageEvent(ChannelEvent):
    """
        Abstraction for events related to messages.
        Since messages are sent in channels, it's derived from ChannelEvent
    """
    message_id : str

class CommunityMessageCreatedEvent(CommunityMessageEvent):
    """When a message is sent to a channel"""
    event : Literal["community_message_created"] = "community_message_created"
    message : Message

class CommunityMessageDeletedEvent(CommunityMessageEvent):
    """When a message is deleted from a channel"""
    event : Literal["community_message_deleted"] = "community_message_deleted"

class CommunityMessageModifiedEvent(CommunityMessageEvent):
    """When a message is edited"""
    event : Literal["community_message_modified"] = "community_message_modified"
    before : Message
    after : Message

class CommunityMessagePingEvent(CommunityMessageEvent):
    """
    When a message contains a ping
    """
    event : Literal["community_message_ping"] = "community_message_ping"

# endregion