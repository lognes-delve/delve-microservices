from datetime import datetime
from typing import List, Literal, Optional, Tuple
from pydantic import BaseModel
from json import loads
from bson import ObjectId
import re

def dump_basemodel_to_json_bytes(m : BaseModel, *, encoding : str = 'utf-8') -> bytes:
    return m.model_dump_json().encode(encoding)

def load_json_bytes(b : bytes, *, encoding : str = 'utf-8') -> dict:
    return loads(b.decode(encoding))


def objectid_fix(d : dict, *, desired_outcome : Literal["oid", "str"] = "oid") -> dict:
    """
        Takes any dictionary that contains an `id` key and returns one with an objectid `_id` instead.
        Alternatively, if the key is `_id` it'll swap it to a string `id` instead.

        It will strictly confine to the desired outcome if `desired_outcome` is not set to null.
        The default behaviour is a toggle.
    """
    # This is actually a horrible function

    tmp = {}

    for k, v in d.items():

        if k == "id" and desired_outcome == "oid":
            tmp["_id"] = ObjectId(v)

        elif k == "_id" and desired_outcome == "str":
            tmp["id"] = str(v)

        elif "id" in k:

            if desired_outcome == "oid":

                if isinstance(v, list) and all([ObjectId.is_valid(vx) for vx in v]):
                    tmp[k] = [ObjectId(vx) for vx in v]

                elif ObjectId.is_valid(v):
                    tmp[k] = ObjectId(v)

                else:
                    tmp[k] = v

            elif desired_outcome == "str":

                if isinstance(v, list) and all([isinstance(vx, ObjectId) for vx in v]):
                    tmp[k] = [str(vx) for vx in v]

                elif isinstance(v, ObjectId):
                    tmp[k] = str(v)

                else:
                    tmp[k] = v

        elif isinstance(v, dict):
            tmp[k] = objectid_fix(v, desired_outcome=desired_outcome)

        else:
            tmp[k] = v

    return tmp

USER_MENTION_PATTERN = re.compile(r"<(@\w{24})>")
ROLE_MENTION_PATTERN = re.compile(r"<(&\w{24})>")

def get_mention_tags_from_content_body(
    c : str
) -> List[str]:
    """
        Returns an array of mention tags prefixed with either:
            - `@` to denote a user mention
            - `&` to denote a role mention
        This should hopefully be more space efficient than returning a tuple
        or something similar
    """

    # Finding the user mentions
    user_mentions = USER_MENTION_PATTERN.findall(c)

    # Finding the user mentions
    role_mentions = ROLE_MENTION_PATTERN.findall(c)

    return [*user_mentions, *role_mentions]

class MessageQueryBuilder(object):
    """Abstraction for building the message lookup pipeline"""

    __community_id : ObjectId
    __channel_id : ObjectId

    __limit : int
    __sort_order : Literal[-1, 1] # 1 = asc, -1 = dsc
    __sent_before : Optional[datetime]
    __sent_after : Optional[datetime]

    def __init__(
        self,
        community_id : str,
        channel_id : str
    ) -> None:
        
        self.__community_id = ObjectId(community_id)
        self.__channel_id = ObjectId(channel_id)
        
        self.__reset_defaults()

    def __reset_defaults(self) -> None:
        self.__limit = 50
        self.__sort_order = -1
        self.__sent_before = None
        self.__sent_after = None

    def set_community_id(self, s : str) -> None:
        self.__community_id = ObjectId(s)

    def set_channel_id(self, s : str) -> None:
        self.__channel_id = ObjectId(s)

    def set_limit(self, n : int) -> None:
        self.__limit = n

    def set_sort_order(self, s : Literal["ASC", "DSC"]) -> None:
        self.__sort_order = 1 if s == "ASC" else -1

    def set_sent_before(self, d : datetime) -> None:
        self.__sent_before = d

    def set_sent_after(self, d : datetime) -> None:
        self.__sent_after = d

    def __get_additional_match_params(self) -> dict:
        additional_match_params = {}

        if self.__sent_after or self.__sent_before:
            additional_match_params["created_at"] = {}

            if self.__sent_after:
                additional_match_params["created_at"]["$gte"] = self.__sent_after

            if self.__sent_before:
                additional_match_params["created_at"]["$lte"] = self.__sent_before

        return additional_match_params

    def build(self) -> List[dict]:
        steps = [
            {"$match" : {
                "community_id" : ObjectId(self.__community_id),
                "channel_id" : ObjectId(self.__channel_id),
                **self.__get_additional_match_params()
            }},
            {
                "$sort" : {"created_at" : self.__sort_order}
            },
            {
                "$limit" : self.__limit
            }
        ]

        self.__reset_defaults()

        return steps


        