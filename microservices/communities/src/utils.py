from typing import Literal
from pydantic import BaseModel
from json import loads
from bson import ObjectId

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
