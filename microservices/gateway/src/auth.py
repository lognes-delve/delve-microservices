from typing import Annotated
from fastapi import (
    WebSocket, 
    Query,
    Cookie,
    WebSocketException,
    status
)
import jwt
from cryptography import x509
from os import getenv
import aiohttp

FIREBASE_SECURE_TOKEN_X509_URL = "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"

async def get_cookie_or_token(
    websocket : WebSocket,
    session : Annotated[str | None, Cookie()] = None,
    token : Annotated[str | None, Query()] = None
) -> str:
    
    if session is None and token is None:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    
    return session or token

firebase_x509 = None

async def fetch_firebase_x509():

    global firebase_x509 # EWWWW GLOBAL VARIABLE
    
    if firebase_x509:
        return firebase_x509

    async with aiohttp.ClientSession() as cs:

        async with cs.get(FIREBASE_SECURE_TOKEN_X509_URL) as resp:

            x509_resp = await resp.json()

    firebase_x509 = x509_resp
    return firebase_x509

async def process_jwt_token(token : str) -> dict:
    """Validates the JWT and returns the encoded payload"""

    decoded_token = jwt.get_unverified_header(token)

    token_kid = decoded_token["kid"]

    firebase_x509s = await fetch_firebase_x509()

    key = x509.load_pem_x509_certificate(
        str(firebase_x509s[token_kid]).encode('utf-8')
    )

    pub_key = key.public_key()

    return jwt.decode(
        token,
        pub_key,
        ['RS256'],
        options=None,
        audience=getenv("FIREBASE_PROJECT_ID")
    )

