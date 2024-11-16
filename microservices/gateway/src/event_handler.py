
from typing import Awaitable, Callable, Dict, List, Type, Union
from delve_common._messages.base import BaseEvent

from .models import GatewayState

# This is gonna suck SO much
class EventHandler(object):

    event_handlers : Dict[str, List[Callable[[dict, GatewayState], Awaitable[None]]]]
    forward_events : List[str]
    gateway_state : GatewayState

    def __init__(self, gateway_state : GatewayState) -> None:
        self.gateway_state = gateway_state
        
        # init defaults
        self.forward_events = []
        self.event_handlers = {}

    def register_handler(
        self, 
        event_type : Union[BaseEvent, str], 
        handler : Callable[[dict, GatewayState], Awaitable[None]]
    ) -> None:
        
        if isinstance(event_type, BaseEvent):
            event_type = event_type.event

        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = [handler]
            return self     # To allow for chainable calls
        
        self.event_handlers[event_type].append(handler)
        return self     # To allow for chainable calls

    async def handle_event(self, event : dict, forward_events : bool = True) -> None:
        

        # If a non-dictionary event pops into the thing, just turn it into a dict.
        if isinstance(event, BaseEvent):
            event = event.model_dump()

        # If the event doesn't have an identifier...
        if "event" not in event:
            raise ValueError(f"Invalid object found in handler. No event found! {event, type(event)}")

        if forward_events and event["event"] in self.forward_events:
            await self.__forward_event(event)

        if event["event"] not in self.event_handlers:
            return
        
        for handler in self.event_handlers[event['event']]:
            await handler(event, self.gateway_state)

    async def __forward_event(self, event : dict) -> None:
        return await self.gateway_state.websocket.send_json(event)

    def add_event_forward(self, event_key : str) -> None:  
        return self.forward_events.append(event_key)
    
    def add_event_forwards(self, *event_keys : Union[List[str]]) -> None:

        if not event_keys: 
            return

        return self.forward_events.extend(event_keys)