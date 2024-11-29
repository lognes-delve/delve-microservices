from datetime import UTC, datetime
from typing import Optional

from bson import ObjectId
from ..models import GatewayState
from copy import copy
from .ack import assert_gateway_readiness
from ..messages import (
    HeartbeatResponse,
    StateResponse, 
    StateRequest
)
from delve_common._messages.communities import (
    CommunityDeletedEvent,
    LeftCommunityEvent,
    CommunityCreatedEvent,
    JoinedCommunityEvent
)
from delve_common._db._database import get_database


# region Util

def util_get_community_redis_channels(community_id : str):
    return [
        f"community_deleted.{community_id}",
        f"community_modified.{community_id}",
    ]

def util_get_channel_redis_channels(community_id : str, channel_id : Optional[str] = "*"):
    return [
        f"channel_created.{community_id}.{channel_id}",
        f"channel_modified.{community_id}.{channel_id}",
        f"channel_deleted.{community_id}.{channel_id}",
    ]

def util_get_member_redis_channels(community_id : str, user_id : Optional[str] = "*"):
    return [
        f"member_joined.{community_id}.{user_id}",
        f"member_left.{community_id}.{user_id}",
        f"member_modified.{community_id}.{user_id}"
    ]

def util_get_role_channels(community_id : str):
    return [
        f"role.created.{community_id}.*",
        f"role_deleted.{community_id}.*",
        f"role_modified.{community_id}.*",
        f"role_reorder.{community_id}"
    ]

def util_get_all_redis_channels(community_id : str):
    return [
        *util_get_community_redis_channels(community_id),
        *util_get_channel_redis_channels(community_id),
        *util_get_member_redis_channels(community_id),
        *util_get_role_channels(community_id)
    ]

# endregion

# 'community_modified'
# "member_modified"
# "channel_modified"
# "channel_created"
# "channel_deleted"

# These are just forwarded, and do not need any additional information
# "community_message_created"
# "community_message_deleted"
# "community_message_modified"
# "community_message_ping"

# "state_response"
async def update_view_state(d : dict, gateway_state : GatewayState) -> None:    
    resp = StateResponse(**d)

    old_state = copy(gateway_state)

    gateway_state.current_channel_id = resp.channel_id
    gateway_state.current_community_id = resp.community_id

    # Subscribe to new message events
    if resp.channel_id and resp.community_id:
        await gateway_state.pubsub.psubscribe(
            f"community_message_sent.{gateway_state.current_community_id}.{gateway_state.current_channel_id}",
            f"community_message_modified.{gateway_state.current_community_id}.{gateway_state.current_channel_id}.*",
            f"community_message_deleted.{gateway_state.current_community_id}.{gateway_state.current_channel_id}.*"
        )

    # Unsubscribe from the old message events
    if old_state.current_channel_id or old_state.current_community_id:
        await gateway_state.pubsub.unsubscribe(
            f"community_message_sent.{old_state.current_community_id}.{old_state.current_channel_id}"
            f"community_message_modified.{old_state.current_community_id}.{old_state.current_channel_id}.*",
            f"community_message_deleted.{old_state.current_community_id}.{old_state.current_channel_id}.*"
        )

    gateway_state.ack.state_request_recv = True

    await assert_gateway_readiness(gateway_state)
    
# "community_deleted"
async def community_deleted_handler(d : dict, gateway_state : GatewayState) -> None:
    resp = CommunityDeletedEvent(**d)

    await gateway_state.pubsub.unsubscribe(*util_get_all_redis_channels(resp.community_id))

# "left_community"
async def left_community_handler(d : dict, gateway_state : GatewayState) -> None:

    resp = LeftCommunityEvent(**d)

    if (gateway_state.user_id == resp.user_id):

        return await gateway_state.pubsub.unsubscribe(
            *util_get_community_redis_channels(
                resp.community_id
            )
        )

# "joined_community"
async def joined_community_handler(d : dict, gateway_state : GatewayState) -> None:

    resp = JoinedCommunityEvent(**d)

    if resp.user_id == gateway_state.user_id:

        return await gateway_state.pubsub.psubscribe(
            *util_get_all_redis_channels(resp.community_id)
        )
    
# "community_created"
async def community_created_handler(d : dict, gateway_state : GatewayState) -> None:

    resp = CommunityCreatedEvent(**d)

    if resp.community.owner_id == gateway_state.user_id:
        await gateway_state.pubsub.psubscribe(*util_get_all_redis_channels(resp.community_id))

async def heartbeat_response_handler(d : dict, gateway_state : GatewayState) -> None:

    resp = HeartbeatResponse(**d)

    db = await get_database()

    await db.get_collection("users").update_one(
        {"_id" : ObjectId(gateway_state.user_id)},
        {"$set" : {"last_seen" : datetime.now(tz=UTC)}}
    )