import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from starlette.requests import Request
from starlette.responses import JSONResponse
from .auth import Casdoor

__all__ = ["router"]

router = APIRouter(tags=["login"])


@router.post("/signin", response_class=JSONResponse)
async def post_signin(
    request: Request,
    code: str = Query(...),
    state: Optional[str] = Query(None),
):
    casdoor: Casdoor = request.app.state.casdoor
    if not casdoor.enabled:
        raise HTTPException(status_code=500, detail="Casdoor is not enabled")
    token = casdoor.sdk.get_oauth_token(code)
    if token.get("error") is not None:
        return token
    logging.debug(f"token: {token}")
    claims = casdoor.sdk.parse_jwt_token(token["access_token"])
    logging.debug(f"claim: {claims}")

    response = JSONResponse(content={"token": token["access_token"]})
    return response
