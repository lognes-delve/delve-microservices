from delve_common._db._database import get_database

async def ensure_vacant_username(username : str) -> bool:

    db = await get_database()

    user_search = await db.get_collection("users").find_one({"username" : username.lower()})

    # Dont do anything with the user data pulled, just return true if there's no user found.
    return user_search is None