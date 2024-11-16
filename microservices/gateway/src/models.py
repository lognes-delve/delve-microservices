from typing import List, Optional
from fastapi import WebSocket
from pydantic import BaseModel, Field
from redis.client import PubSub

class GatewayState(object):

    def __init__(self, websocket : WebSocket, user_id : str, pubsub : PubSub) -> None:

        self.websocket = websocket
        self.user_id = user_id
        self.pubsub = pubsub

        # Init defaults
        self.ack = Acknowledgements()
        self.current_channel_id = None
        self.current_community_id = None 

    websocket : WebSocket
    pubsub : PubSub
    user_id : str

    current_community_id : Optional[str]
    current_channel_id : Optional[str]

    ack : "Acknowledgements"

    @property
    def no_channel_in_view(self) -> bool:
        return self.current_channel_id is None and self.current_community_id is None
    
    @property
    def outstanding_ack(self) -> List[str]:
        """Returns the keys of outstanding acknowledgements"""
        return [k for k in self.ack.model_dump() if not k]

class Acknowledgements(BaseModel):
    """Whether or not certain acknowledgements were recieved"""
    
    websocket_ready : bool = False
    state_request_recv : bool = False