from ..models import GatewayState
from ..messages import StateResponse, StateRequest
from copy import copy
from .ack import assert_gateway_readiness

async def update_view_state(d : dict, gateway_state : GatewayState) -> None:    
    resp = StateResponse(**d)

    old_state = copy(gateway_state)

    gateway_state.current_channel_id = resp.channel_id
    gateway_state.current_community_id = resp.community_id

    # Subscribe to new message events
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
    