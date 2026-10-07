import logging
from datetime import datetime, timedelta, timezone

import aiohttp
from casdoor import CasdoorSDK
from fastapi import HTTPException
from pydantic import BaseModel
from starlette.requests import Request

__all__ = [
    "auth_bearer_token",
    "CasdoorConfig",
]

ROLE = None  # "agentsociety:user"
DEMO_USER_TOKEN = "DEMO_USER_TOKEN"
DEMO_USER_ID = "DEMO"


class CasdoorConfig(BaseModel):
    enabled: bool = False
    client_id: str
    client_secret: str
    application_name: str
    endpoint: str = "https://login.fiblab.net"
    org_name: str = "fiblab"
    certificate: str


class Casdoor:
    def __init__(
        self,
        config: CasdoorConfig,
    ):
        self.enabled = config.enabled
        if not self.enabled:
            self._sdk = None
            return
        self._sdk = CasdoorSDK(
            endpoint=config.endpoint,
            client_id=config.client_id,
            client_secret=config.client_secret,
            certificate=config.certificate,
            application_name=config.application_name,
            org_name=config.org_name,
        )
        self._user_cache = {}  # 用户缓存
        self._cache_expiry = {}  # 缓存过期时间

    @property
    def sdk(self) -> CasdoorSDK:
        assert self._sdk is not None
        return self._sdk

    async def get_user_by_id(self, user_id: str):
        assert self._sdk is not None
        # 检查缓存是否有效
        now = datetime.now(timezone.utc)
        if user_id in self._user_cache and self._cache_expiry.get(user_id, now) > now:
            return self._user_cache[user_id]

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.sdk.endpoint}/api/get-user",
                params={
                    "userId": user_id,
                    "clientId": self.sdk.client_id,
                    "clientSecret": self.sdk.client_secret,
                },
            ) as res:
                if res.status != 200:
                    return None
                data = await res.json()
                if data["status"] != "ok":
                    return None

                # 更新缓存
                self._user_cache[user_id] = data["data"]
                self._cache_expiry[user_id] = now + timedelta(seconds=5)
                return data["data"]


async def auth_bearer_token(request: Request):
    casdoor: Casdoor = request.app.state.casdoor
    if not casdoor.enabled:
        return "dev"

    authorization = request.headers.get("Authorization")
    if authorization is None:
        # try to get authorization from form
        form = await request.form()
        authorization = form.get("authorization")
        if authorization is None or not isinstance(authorization, str):
            # 401 Unauthorized
            raise HTTPException(status_code=401, detail="Unauthorized")

    if not authorization.startswith("Bearer "):
        # 401 Unauthorized
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization[7:]
    logging.debug(f"token: {token}")
    if token == DEMO_USER_TOKEN:
        return DEMO_USER_ID
    claims = None
    try:
        claims = casdoor.sdk.parse_jwt_token(token)
    except Exception:
        import traceback

        traceback.print_exc()
        # 401 Unauthorized
        raise HTTPException(status_code=401, detail="Unauthorized")
    if claims is None:
        # 401 Unauthorized
        raise HTTPException(status_code=401, detail="Unauthorized")
    logging.debug(f"claim: {claims}")
    # 从casdoor获取用户角色
    user = await casdoor.get_user_by_id(claims["sub"])
    if user is None:
        # 401 Unauthorized
        raise HTTPException(status_code=401, detail="Unauthorized")
    logging.debug(f"user: {user}")
    if ROLE is None:
        return user["id"]
    roles = user["roles"]
    for role in roles:
        if role["name"] == ROLE and role["isEnabled"]:
            return user["id"]
    # 403 Forbidden
    raise HTTPException(status_code=403, detail="Forbidden")
