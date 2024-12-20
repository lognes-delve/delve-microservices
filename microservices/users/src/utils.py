from delve_common._db._database import get_database
from bson import ObjectId
from typing import Literal

async def ensure_vacant_username(username : str) -> bool:

    db = await get_database()

    user_search = await db.get_collection("users").find_one({"username" : username.lower()})

    # Dont do anything with the user data pulled, just return true if there's no user found.
    return user_search is None

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