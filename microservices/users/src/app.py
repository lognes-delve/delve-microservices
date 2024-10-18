from datetime import UTC, datetime
from typing import Annotated, Optional, Union, NewType
from fastapi import FastAPI, Depends
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
import firebase_admin.auth
from starlette.responses import JSONResponse
from bson import ObjectId
import firebase_admin
import asyncio
import functools
from os import getenv
import json
from pymongo import ReturnDocument
from pydantic import BaseModel

from delve_common._db._database import Database, get_database
from delve_common._types._dtos import User
from delve_common.exceptions import DelveHTTPException

from .models import UserRegistration
from .utils import ensure_vacant_username

app = FastAPI()

X_USER_HEADER = APIKeyHeader(name="X-UserInfo")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class EMPTY(BaseModel): pass # sentinel class

firebase_admin.initialize_app(
    firebase_admin.credentials.Certificate(json.loads(getenv("FIREBASE_CREDENTIALS"))), 
    options={"projectId" : getenv("FIREBASE_PROJECT_ID")})

Database.using_app(app)

@app.post("/register")
async def register_user(
    data : UserRegistration
) -> User:
    """
        Registers a user
    """

    # Get the database
    db = await get_database()

    user_id = ObjectId()

    # Ensure that the username the user is requesting is not already taken.
    uname_check = await ensure_vacant_username(data.username)

    if not uname_check:
        raise DelveHTTPException(
            status_code=400, detail="Username is already taken",
            identifier="username-already-taken",
            additional_metadata={"username" : data.username}
        )

    # Build the user dto from the registration model
    user = User(
        id = str(user_id),
        display_name = data.display_name or data.username,
        username = data.username
    )

    # Run the syncronous firebase registration function in a thread instead of blocking stuff
    try:
        user_record = await asyncio.get_event_loop().run_in_executor(
            None,
            functools.partial(
                firebase_admin.auth.create_user,
                **{
                    "uid" : str(user_id),
                    "display_name" : data.display_name,
                    "email" : data.email,
                    "password" : data.password
                }
            )
        )
    except Exception:
        raise DelveHTTPException(
            status_code=500, detail="Failed to create user",
            identifier="user-creation-failed",
            additional_metadata={
                "user" : user.model_dump()
            }
        )

    # Sanity check
    assert user_record.uid == str(user_id), "Inconsistent user record"

    inserted_record = await db.get_collection("users").insert_one(user.model_dump())

    # If the user doesn't get inserted into mongodb...
    if inserted_record.inserted_id is None:

        # Delete the hanging firebase user
        await asyncio.get_event_loop().run_in_executor(
            None,
            functools.partial(
                firebase_admin.auth.delete_user, user_id
            )
        )

        # Raise an http exception stating the issue
        raise DelveHTTPException(
            status_code=500, detail="Failed to create user due to unknown error",
            identifier="failed-to-create-user",
            additional_metadata={"user" : user.model_dump()}
        )
    
    # If everything goes well, return the user object
    return user
    
@app.get("/username_check")
async def username_check(
    username : str
) -> bool:
    """
        Returns a 200 request if the username is available
        If the username provided is taken, this endpoint raises a 400 Bad Request error
    """
    resp = await ensure_vacant_username(username)

    if not resp:
        raise DelveHTTPException(
            status_code=400,
            detail="Username already taken!",
            additional_metadata={"username" : username.lower()}
        )
    
    return True

@app.get("/me")
async def get_myself(x_user : Annotated[str, Depends(X_USER_HEADER)]) -> User:
    print(x_user)

    return await get_user(
        x_user=x_user,
        user_id=x_user
    )

@app.delete("/delete")
async def delete_this_user(x_user : Annotated[str, Depends(X_USER_HEADER)]) -> None:
    pass
    
@app.patch("/")
async def update_user(
    x_user : Annotated[str, Depends(X_USER_HEADER)],
    display_name : Optional[Union[EMPTY, str, None]] = EMPTY,
    username : Optional[Union[EMPTY, str]] = EMPTY,
    bio : Optional[Union[EMPTY, str, None]] = EMPTY,
    pronouns : Optional[Union[EMPTY, str, None]] = EMPTY
) -> User:
    
    # A mapping to hold all valid differences until we're done our checks
    diff = {}

    if not isinstance(display_name, EMPTY):
        diff['display_name'] = display_name

    if not isinstance(username, EMPTY):
        is_vacant = await ensure_vacant_username(username)

        if not is_vacant:
            raise DelveHTTPException(
                status_code=400, detail="That username is already taken",
                additional_metadata={"invalid-update-field" : "username"}
            )
        
        diff["username"] = username

    if not isinstance(bio, EMPTY):
        diff["bio"] = bio

    if not isinstance(pronouns, EMPTY):
        diff["pronouns"] = pronouns

    # If it gets past all the checks, update the "edited_at" field as well for the user
    diff["edited_at"] = datetime.now(tz=UTC)

    # Fetch the database
    db = await get_database()

    print(diff)

    # Update the user
    record = await db.get_collection("users").find_one_and_update(
        filter = {"id" : x_user}, update = {"$set" : diff}, return_document = ReturnDocument.AFTER
    )

    # If no record returned, assume the update failed unexpectedly
    if record is None:
        raise DelveHTTPException(
            status_code=500, detail="Something unexpected occurred!",
            identifier="failed-to-update-unexpected-error",
            additional_metadata={"diff" : diff, "x_user" : x_user}
        )
    
    # If the record isn't null, return that as the updated user in response
    return User(**record)
    

@app.get("/{user_id}")
async def get_user(
    x_user : Annotated[str, Depends(X_USER_HEADER)], # basically just requires an authenticated user from service mesh.
    user_id : str
) -> User:
    """Retrieves a user record"""

    db = await get_database()

    record = await db.get_collection("users").find_one(
        {"id" : user_id}
    )

    if record is None:
        raise DelveHTTPException(
            status_code=404, detail="Couldn't find user with that id",
            identifier="user-not-found",
            additional_metadata={"user_searched_for" : user_id}
        )

    return User(**record)