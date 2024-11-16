from ..models import GatewayState
from ..messages import GatewayReady

async def assert_gateway_readiness(gateway_state : GatewayState) -> None:

    if not gateway_state.ack.websocket_ready:
        gateway_state.ack.websocket_ready = True
        await gateway_state.websocket.send_json(GatewayReady().model_dump())