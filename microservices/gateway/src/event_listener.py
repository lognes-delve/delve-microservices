from typing import AsyncIterator, Callable, Dict, List, Self, Tuple, Type, Union
from delve_common._messages.base import BaseEvent
import aiostream

# I thought the event handler was gonna be bad. This is so much worse.
class EventListener(object):
    
    event_producers : Dict[str, AsyncIterator[dict]]
    producer_restrictions : Dict[str, Callable[[str], bool]]

    def __init__(self):

        # init defaults
        self.event_producers = {}
        self.producer_restrictions = {}

    def __create_listener_event_callable(
            self, valid_keys = List[str]) -> Callable[[str], bool]:
        
        def f(event_key : str) -> bool:
            return event_key in valid_keys
        
        return f
    
    async def __wrapped_restrictive_iter(self, identifier : str, iter : AsyncIterator[dict]) -> AsyncIterator[dict]:
        async for msg in iter:
            
            if identifier in self.producer_restrictions:
                if self.producer_restrictions[identifier](msg['event']):
                    yield msg
                    continue

            yield msg

    def __get_all_wrapped_restrictive_iters(self) -> List[AsyncIterator[dict]]:
        return [self.__wrapped_restrictive_iter(k, p) for k, p in self.event_producers.items()]

    def add_event_source(
        self,
        identifier : str,
        async_iter : AsyncIterator[dict],
        *,
        valid_events : Union[List[Type[BaseEvent]], None] = None,
    ) -> Self:
        
        self.event_producers[identifier] = async_iter()

        if valid_events is not None:
            self.producer_restrictions[identifier] = self.__create_listener_event_callable(
                valid_keys=valid_events
            )

        return self # to allow for function call chaining

    def get_stream(self) -> aiostream.Stream:
        return aiostream.stream.merge(
            *self.__get_all_wrapped_restrictive_iters()
        )
