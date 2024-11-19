from typing import Literal, Optional
from delve_common._messages.base import BaseEvent

class StateRequest(BaseEvent):
    event : Literal["state_request"] = "state_request"

class StateResponse(BaseEvent):
    event : Literal["state_response"] = "state_response"

    channel_id : Optional[str]
    community_id : Optional[str]

class GatewayReady(BaseEvent):
    event : Literal["gateway_ready"] = "gateway_ready"

class GatewayNotReady(BaseEvent):
    event: Literal["gateway_not_ready"] = "gateway_not_ready"

class HeartbeatRequest(BaseEvent):
    event: Literal["heartbeat_request"] = "heartbeat_request"

class HeartbeatResponse(BaseEvent):
    event: Literal["heartbeat_response"] = "heartbeat_response"

