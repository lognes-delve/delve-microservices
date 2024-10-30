from typing import Literal, Union
from ..base import BaseEvent
from pydantic import BaseModel, Field

class StateChange(BaseEvent):
    event: Literal["state_change"] = "state_change"

class ViewStateChange(StateChange):
    event: Literal["view_state_change"] = "view_state_change"

    view : Union["ChannelView", "HomeView"]

# region ViewStates

class ViewState(BaseModel):
    """Abstract format for a view"""
    type : str

class ChannelView(BaseModel):
    """Provides information on what channel is currently being viewed"""
    type : Literal["channel_view"] = "channel_view"
    channel_id : str
    community_id : str

class HomeView(BaseModel):
    """Describes that the home view is currently being viewed"""
    type : Literal["home_view"] = "home_view"

# endregion