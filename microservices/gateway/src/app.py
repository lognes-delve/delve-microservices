from typing import Annotated, AsyncIterator
from fastapi import Depends, FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import json
from asyncio import Queue

from delve_common._db._database import Database, get_client
from delve_common._db._redis import DelveRedis, get_redis

from .models import GatewayState
from .event_handler import EventHandler
from .event_listener import EventListener
from .messages import StateResponse, StateRequest
from .auth import get_cookie_or_token, process_jwt_token

from .event_handlers.state_handlers import (
    update_view_state
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Database.using_app(app)
DelveRedis.using_app(app)

@app.websocket("/")
async def websocket_gateway(
    websocket : WebSocket,
    token : Annotated[str, Depends(get_cookie_or_token)]
):
    
    if not token:
        raise ValueError("Not auth'n'ed.")

    # Get the user id from the jwt provided via cookie or query    
    auth_payload = await process_jwt_token(token)
    user_id = auth_payload['sub']

    redis = await get_redis()
    redis_pubsub = redis.pubsub(
        ignore_subscribe_messages=True
    )

    gateway_state = GatewayState(websocket, user_id, pubsub=redis_pubsub)
    internal_queue = []

    await websocket.accept()
    await redis_pubsub.connect() # Ensure that redis pub/sub connection is made

    # region Building the AsyncIterators for the different sources messages will flow in from
    # This recieves payloads from clients
    async def from_ws_iterator() -> AsyncIterator[dict]:
        async for message in websocket.iter_json():
            yield message


    # This recieves payloads from redis
    async def from_redis_pubsub_iterator() -> AsyncIterator[dict]:
        while True:
            msg = await redis_pubsub.get_message(timeout=60)
            if msg is None: continue
            yield json.loads((bytes(msg['data'])).decode('utf-8'))  

    # Add the sources to the event listener
    event_listener = EventListener()
    event_listener.add_event_source("ws", from_ws_iterator, valid_events=[StateResponse])
    event_listener.add_event_source("redis", from_redis_pubsub_iterator)
    # endregion

    event_handler = EventHandler(gateway_state=gateway_state)
    event_handler.add_event_forward("state_request")
    event_handler.register_handler(
        "state_response", update_view_state
    )

    # All of the message forwards
    event_handler.add_event_forwards(
        "community_message_created",
        "community_message_deleted",
        "community_message_modified",
        "community_message_ping"
    )

    # Put an initial event query to ask for the client's state
    internal_queue.append(StateRequest())

    while True:
        # Handles incoming events from the internal event queue
        while len(internal_queue):
            internal_event = internal_queue.pop(0)
            await event_handler.handle_event(internal_event)

        # Handles incoming events from external sources
        async with event_listener.get_stream().stream() as streamer:
            async for message in streamer:
                await event_handler.handle_event(
                    message, 
                    forward_events=True
                )