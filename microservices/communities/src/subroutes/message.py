
from datetime import UTC, datetime
from bson import ObjectId
from delve_common._types._dtos._message import Message, MessageContent
from fastapi import Body, Depends, Query
from fastapi.routing import APIRouter
from typing import Annotated, List, Literal, Optional
from copy import copy
from pymongo import ReturnDocument

from ..constants import X_USER_HEADER
from ..utils import (
    MessageQueryBuilder,
    dump_basemodel_to_json_bytes, 
    get_mention_tags_from_content_body, 
    objectid_fix,
)

from delve_common._db._database import get_database
from delve_common._db._redis import get_redis
from delve_common.exceptions import DelveHTTPException
from ..messaging.messages.out.communities import (
    CommunityMessageCreatedEvent,
    CommunityMessageDeletedEvent,
    CommunityMessageModifiedEvent,
    CommunityMessagePingEvent
)

# --- MESSAGE ENDPOINTS (MAY REQUIRE SOME GATEWAY INTEGRATION)
# --- gateway will need a pub/sub message broker (FUCK YOU DISTRIBUTED REDIS.)
# CREATE A MESSAGE
# FETCH A SINGLE MESSAGE
# RETURN MANY MESSAGES
# DELETE A MESSAGE
# UPDATE A MESSAGE
# SEMANTIC MESSAGE SEARCH

router = APIRouter()

@router.post("/{community_id}/channels/{channel_id}/messages")
async def create_new_message(
    user_id : Annotated[str, Depends(X_USER_HEADER)],
    community_id : str,
    channel_id : str,
    message_body : MessageContent = Body()
) -> Message:
    
    db = await get_database()
    redis = await get_redis()

    search_for_member = await db.get_collection("members").find_one(
        {"user_id" : ObjectId(user_id)}
    )

    if not search_for_member:
        raise DelveHTTPException(
            status_code=401,
            detail="User is not a member of this community",
            identifier="user_not_member"
        )

    mentions = get_mention_tags_from_content_body(message_body.text)
    
    message = Message(
        id = str(ObjectId()),
        author_id = user_id,
        channel_id = channel_id,
        community_id=community_id,
        content=message_body,
        mentions = mentions
    )

    resp = await db.get_collection("community_messages").insert_one(
        objectid_fix(message.model_dump(), desired_outcome="oid")
    )

    if not resp.inserted_id:
        raise DelveHTTPException(
            status_code=500,
            detail="Something went very wrong",
            identifier="unknown_error_creating_message"
        )
    
    await redis.publish(
        f"community_message_sent.{community_id}.{channel_id}",
        dump_basemodel_to_json_bytes(
            CommunityMessageCreatedEvent(
                community_id=community_id,
                channel_id=channel_id,
                message_id=message.id,
                message=message
            )
        )
    )

    # handle the mentions
    # NOTE: `m_id` is stripped of the denoting prefix character
    for m_id in [m[1:] for m in mentions if m.startswith("@")]:
        await redis.publish(
            f"community_user_ping.{m_id}",
            dump_basemodel_to_json_bytes(
                CommunityMessagePingEvent(
                    community_id=community_id,
                    channel_id=channel_id,
                    message_id=message.id
                )
            )
        )
    
    return message


@router.get("/{community_id}/channels/{channel_id}/messages")
async def get_channel_messages(
    user_id : Annotated[str, Depends(X_USER_HEADER)],
    community_id : str,
    channel_id : str,
    limit : Optional[int] = Query(default=50, le=100),
    sent_before : Optional[datetime] = Query(default=None),
    sent_after : Optional[datetime] = Query(default=None),
    sort_order : Optional[Literal["ASC", "DSC"]] = Query(default="DSC")
) -> List[Message]:
    
    db = await get_database()

    search_for_member = await db.get_collection("members").find_one(
        {"user_id" : ObjectId(user_id)}
    )

    if not search_for_member:
        raise DelveHTTPException(
            status_code=401,
            detail="User is not a member of this community",
            identifier="user_not_member"
        )

    mqb = MessageQueryBuilder(community_id=community_id, channel_id=channel_id)

    # Setting the required steps
    mqb.set_limit(limit)
    mqb.set_sort_order(sort_order)

    # Probably a horrible way to do this
    if sent_before:
        mqb.set_sent_before(sent_before)
    
    if sent_after:
        mqb.set_sent_after(sent_after)

    pipeline = db.get_collection("community_messages").aggregate(mqb.build())

    return [Message(**objectid_fix(msg, desired_outcome="str")) async for msg in pipeline]

# TODO: Doing this later as it is not imperative to be finished right away
@router.get("/{community_id}/channels/{channel_id}/messages/search")
async def message_search() -> List[Message]:
    return # TODO:

@router.get("/{community_id}/channels/{channel_id}/messages/{message_id}")
async def get_message_by_id(
    user_id : Annotated[str, Depends(X_USER_HEADER)],
    community_id : str,
    channel_id : str,
    message_id : str
) -> Message:
    
    db = await get_database()

    search_for_member = await db.get_collection("members").find_one(
        {"user_id" : ObjectId(user_id)}
    )

    if not search_for_member:
        raise DelveHTTPException(
            status_code=401,
            detail="User is not a member of this community",
            identifier="user_not_member"
        )
    
    # Some of this query is technically not needed, but I'd rather be safe than sorry
    resp = await db.get_collection("community_messages").find_one(
        {"_id" : ObjectId(message_id), "community_id" : ObjectId(community_id), "channel_id" : ObjectId(channel_id)}
    )

    if not resp:
        raise DelveHTTPException(
            status_code=404,
            detail="Failed to find message",
            identifier="message_not_found"
        )

    return Message(**objectid_fix(resp, desired_outcome="str"))

@router.delete("/{community_id}/channels/{channel_id}/messages/{message_id}")
async def delete_message(
    user_id : Annotated[str, Depends(X_USER_HEADER)],
    community_id : str,
    channel_id : str,
    message_id : str
) -> None:

    db = await get_database()
    redis = await get_redis()

    search_for_member = await db.get_collection("members").find_one(
        {"user_id" : ObjectId(user_id)}
    )

    if not search_for_member:
        raise DelveHTTPException(
            status_code=401,
            detail="User is not a member of this community",
            identifier="user_not_member"
        )
    
    resp = await db.get_collection("community_messages").find_one(
        {"_id" : ObjectId(message_id), "community_id" : ObjectId(community_id), "channel_id" : ObjectId(channel_id)}
    )

    if not resp:
        raise DelveHTTPException(
            status_code=404,
            detail="Failed to find that message",
            identifier="message_not_found"
        )

    # TODO<advanced-perms>: Moderation should permit users with certain permissions to delete messages for others
    if str(resp["author_id"]) != user_id:
        raise DelveHTTPException(
            status_code=401,
            detail="Lacking permissions",
            identifier="lacking-permissions"
        )
    
    # -- If we get to this point we assume that the message exists and the user has the permissions to delete it
    resp = await db.get_collection("community_messages").delete_one({"_id" : ObjectId(message_id)})
    
    await redis.publish(
        f"community_message_deleted.{community_id}.{channel_id}.{message_id}",
        dump_basemodel_to_json_bytes(
            CommunityMessageDeletedEvent(
                community_id=community_id,
                channel_id=channel_id,
                message_id=message_id
            )
        )
    )
    
    return

# I actually hated writing this endpoint
@router.patch("/{community_id}/channels/{channel_id}/messages/{message_id}")
async def edit_message(
    user_id : Annotated[str, Depends(X_USER_HEADER)],
    community_id : str,
    channel_id : str,
    message_id : str,
    new_message_content : MessageContent = Body()
) -> Message:
    
    db = await get_database()
    redis = await get_redis()

    search_for_member = await db.get_collection("members").find_one(
        {"user_id" : ObjectId(user_id)}
    )

    if not search_for_member:
        raise DelveHTTPException(
            status_code=401,
            detail="User is not a member of this community",
            identifier="user_not_member"
        )
    
    resp = await db.get_collection("community_messages").find_one(
        {"_id" : ObjectId(message_id), "community_id" : ObjectId(community_id), "channel_id" : ObjectId(channel_id)}
    )

    if not resp:
        raise DelveHTTPException(
            status_code=404,
            detail="Failed to find that message",
            identifier="message_not_found"
        )
    
    # NOTE: This implementation is fine, as the user should be 
    # able to see a message but they might not be able to edit it.
    if str(resp["author_id"]) != user_id:
        raise DelveHTTPException(
            status_code=401,
            detail="Lacking permissions",
            identifier="lacking-permissions"
        )
    
    before_message = Message(**objectid_fix(resp, desired_outcome="str"))

    after_message = copy(before_message)
    after_message.content = new_message_content

    # Get all of the mentions from the new message content body
    recalc_mentions = get_mention_tags_from_content_body(new_message_content.text)

    # Find all uniquely new mentions that exist in the new content body
    diff_mentions = [i for i in recalc_mentions if i not in before_message.mentions]
    
    # Assign the new mention data to the after_message clone thingamajig
    after_message.mentions = recalc_mentions

    # Update the edited_at timestamp
    after_message.edited_at = datetime.now(tz=UTC)

    replace_resp = await db.get_collection("community_messages").find_one_and_replace(
        {"_id" : ObjectId(message_id)},
        objectid_fix(after_message.model_dump(), desired_outcome="oid"),
        return_document = ReturnDocument.AFTER
    )

    if not replace_resp:
        raise DelveHTTPException(
            status_code=500,
            detail="Something went really wrong",
            identifier="nightmare_error"
        )

    await redis.publish(
        f"community_message_modified.{community_id}.{channel_id}.{message_id}",
        dump_basemodel_to_json_bytes(
            CommunityMessageModifiedEvent(
                community_id=community_id,
                channel_id=channel_id,
                message_id=message_id,
                before=before_message,      # These should dump fine because they're also basemodels
                after=after_message         # These should dump fine because they're also basemodels
            )
        )
    )

    # handle the uniquely new mentions, because we LOVE sending new pings
    # NOTE: `m_id` is stripped of the denoting prefix character
    for m_id in [m[1:] for m in diff_mentions if m.startswith("@")]:
        await redis.publish(
            f"community_user_ping.{m_id}",
            dump_basemodel_to_json_bytes(
                CommunityMessagePingEvent(
                    community_id=community_id,
                    channel_id=channel_id,
                    message_id=after_message.id
                )
            )
        )

    return after_message


__all__ = [router]