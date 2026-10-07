"""Shared bearer-token and artifact-lane access helpers."""

from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass

from fastapi import Request


PUBLIC_ARTIFACT_LANE = "downloadable"
TOKEN_ARTIFACT_LANES = frozenset({"published", "staging"})
BLOCKED_ARTIFACT_LANES = frozenset({"control"})
KNOWN_ARTIFACT_LANES = frozenset(
    {PUBLIC_ARTIFACT_LANE, *TOKEN_ARTIFACT_LANES, *BLOCKED_ARTIFACT_LANES}
)


@dataclass(frozen=True)
class ArtifactTokenRecord:
    token: str
    label: str | None = None

    @property
    def token_id(self) -> str:
        return hashlib.sha256(self.token.encode("utf-8")).hexdigest()[:8]


def artifact_token_records(raw: str | None = None) -> tuple[ArtifactTokenRecord, ...]:
    value = str(
        os.getenv("ARTIFACT_ACCESS_TOKENS", "") if raw is None else raw
    ).strip()
    if not value:
        return ()

    records: list[ArtifactTokenRecord] = []
    for item in value.split(","):
        entry = item.strip()
        if not entry:
            continue
        if "=" in entry:
            label, token = entry.split("=", 1)
            label = label.strip()
            token = token.strip()
            if label and token:
                records.append(ArtifactTokenRecord(token=token, label=label))
                continue
        records.append(ArtifactTokenRecord(token=entry))
    return tuple(records)


def artifact_bearer_token(request: Request) -> str | None:
    header = str(request.headers.get("authorization") or "").strip()
    if not header.lower().startswith("bearer "):
        return None
    token = header.split(" ", 1)[1].strip()
    return token or None


def match_artifact_token(token: str | None) -> ArtifactTokenRecord | None:
    provided = str(token or "").strip()
    if not provided:
        return None
    for record in artifact_token_records():
        if hmac.compare_digest(provided, record.token):
            return record
    return None


def get_artifact_token_record(request: Request) -> ArtifactTokenRecord | None:
    return match_artifact_token(artifact_bearer_token(request))


def artifact_lane_requires_token(lane: str) -> bool:
    return str(lane or "").strip().lower() in TOKEN_ARTIFACT_LANES


def artifact_lane_is_public(lane: str) -> bool:
    return str(lane or "").strip().lower() == PUBLIC_ARTIFACT_LANE

