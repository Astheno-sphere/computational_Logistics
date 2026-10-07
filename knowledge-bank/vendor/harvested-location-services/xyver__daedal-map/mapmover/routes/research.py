"""Research mode API router endpoints."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from mapmover import logger
from mapmover.auth_context import build_session_cache_key, get_authenticated_user_async
from mapmover.logging_analytics import log_app_error, log_conversation
from mapmover.research_chat_helpers import _word_chunks
from mapmover.research_corpus import (
    _annotate_manifest_saved_corpus_state,
    _build_browser_install_manifest,
    _decode_browser_source_artifact_payloads,
    _json_safe_value,
    _load_saved_corpus_for_user,
    _read_browser_artifact_bytes,
    _restore_browser_install_source_snapshots,
)
from mapmover.research_lane_runtime import (
    json_dumps_safe,
    research_request_id,
)
from mapmover.research_route_runtime import (
    prepare_research_chat_route_context,
    settle_and_log_research_turn,
)
from mapmover.research_service import (
    get_manifest,
    load_saved_corpus,
    load_url_corpus,
    progress_heartbeat,
    run_turn,
    run_turn_with_progress,
)
from mapmover.routes.disasters.helpers import msgpack_error, msgpack_response
from mapmover.routes.chat_shared import (
    build_chat_error_payload,
    build_provider_error_payload,
    decode_json_or_msgpack_body,
    decode_request_body,
)
from mapmover.runtime.chat_route_support import (
    anonymous_turn_limit_rejection_payload,
    build_chat_gate_log_metadata,
    build_usage_recorders,
    register_anonymous_chat_turn,
)
from mapmover.runtime.sse import SSE_HEADERS, encode_sse, progress_payload, stage_payload


router = APIRouter()


@router.post("/api/research/corpus")
async def research_corpus_endpoint(req: Request):
    try:
        body = await decode_request_body(req)
        frontend_session_id = body.get("sessionId", "anonymous")
        auth_user = await get_authenticated_user_async(req)
        session_id = build_session_cache_key(frontend_session_id, auth_user)
        return msgpack_response(get_manifest(session_id))
    except Exception as exc:
        logger.exception("Research corpus snapshot error")
        return msgpack_error(str(exc), 500)


@router.post("/api/research/load-saved-corpus")
async def research_load_saved_corpus_endpoint(req: Request):
    try:
        body = await decode_request_body(req)
        corpus_id = str(body.get("corpusId") or "").strip()
        if not corpus_id:
            return msgpack_error("No corpusId provided", 400)

        auth_user = await get_authenticated_user_async(req)
        user_id = (auth_user or {}).get("id")
        if not user_id:
            return msgpack_error("Authentication required to load a saved corpus", 401)

        frontend_session_id = body.get("sessionId", "anonymous")
        session_id = build_session_cache_key(frontend_session_id, auth_user)
        saved_corpus = _load_saved_corpus_for_user(user_id, corpus_id)
        if not saved_corpus:
            return msgpack_error("Saved corpus not found", 404)

        return msgpack_response(load_saved_corpus(session_id, saved_corpus))
    except Exception as exc:
        logger.exception("Research saved corpus load error")
        return msgpack_error(str(exc), 500)


@router.post("/api/research/load-url-corpus")
async def research_load_url_corpus_endpoint(req: Request):
    try:
        body = await decode_request_body(req)
        auth_user = await get_authenticated_user_async(req)
        frontend_session_id = body.get("sessionId", "anonymous")
        session_id = build_session_cache_key(frontend_session_id, auth_user)
        return msgpack_response(load_url_corpus(
            session_id,
            body.get("packIds") or body.get("pack_ids"),
            catalog_surface="research",
        ))
    except ValueError as exc:
        return msgpack_error(str(exc), 400)
    except Exception as exc:
        logger.exception("Research URL corpus load error")
        return msgpack_error(str(exc), 500)


@router.post("/api/research/browser-save/install-manifest")
async def research_build_browser_install_manifest_endpoint(req: Request):
    wants_msgpack = "application/msgpack" in str(req.headers.get("accept") or "").lower()
    try:
        body = await decode_json_or_msgpack_body(req)
        corpus_id = str(body.get("corpusId") or "").strip()
        if not corpus_id:
            payload = {"ok": False, "error": "No corpusId provided"}
            return msgpack_response(payload, status_code=400) if wants_msgpack else JSONResponse(payload, status_code=400)

        auth_user = await get_authenticated_user_async(req)
        user_id = (auth_user or {}).get("id")
        if not user_id:
            payload = {"ok": False, "error": "Authentication required"}
            return msgpack_response(payload, status_code=401) if wants_msgpack else JSONResponse(payload, status_code=401)

        saved_corpus = _load_saved_corpus_for_user(user_id, corpus_id)
        if not saved_corpus:
            payload = {"ok": False, "error": "Saved corpus not found"}
            return msgpack_response(payload, status_code=404) if wants_msgpack else JSONResponse(payload, status_code=404)

        install_manifest = _build_browser_install_manifest(saved_corpus)
        payload = _json_safe_value({
            "ok": True,
            "install_manifest": install_manifest,
        })
        return msgpack_response(payload) if wants_msgpack else JSONResponse(payload)
    except ValueError as exc:
        payload = {"ok": False, "error": str(exc)}
        return msgpack_response(payload, status_code=409) if wants_msgpack else JSONResponse(payload, status_code=409)
    except Exception as exc:
        logger.exception("Research browser install-manifest error")
        payload = {"ok": False, "error": str(exc)}
        return msgpack_response(payload, status_code=500) if wants_msgpack else JSONResponse(payload, status_code=500)


@router.get("/api/research/browser-save/source-artifact/{corpus_id}/{source_id}")
async def research_browser_source_artifact_endpoint(corpus_id: str, source_id: str, req: Request):
    try:
        corpus_id = str(corpus_id or "").strip()
        source_id = str(source_id or "").strip()
        if not corpus_id or not source_id:
            return JSONResponse({"ok": False, "error": "Missing corpus_id or source_id"}, status_code=400)

        auth_user = await get_authenticated_user_async(req)
        user_id = (auth_user or {}).get("id")
        if not user_id:
            return JSONResponse({"ok": False, "error": "Authentication required"}, status_code=401)

        saved_corpus = _load_saved_corpus_for_user(user_id, corpus_id)
        if not saved_corpus:
            return JSONResponse({"ok": False, "error": "Saved corpus not found"}, status_code=404)

        install_manifest = _build_browser_install_manifest(saved_corpus)
        source_entry = next(
            (entry for entry in install_manifest.get("sources") or [] if str(entry.get("source_id") or "").strip() == source_id),
            None,
        )
        if not source_entry:
            return JSONResponse({"ok": False, "error": "Source is not part of the saved corpus"}, status_code=404)

        artifact = source_entry.get("browser_artifact") or {}
        storage_key = str(artifact.get("storage_key") or "").strip()
        artifact_bytes, content_type = _read_browser_artifact_bytes(storage_key)
        headers = {
            "Content-Length": str(len(artifact_bytes)),
            "Cache-Control": "private, max-age=300",
            "Content-Disposition": f'inline; filename="{source_id}_runtime_snapshot_v1.json.gz"',
            "X-DaedalMap-Source-Id": source_id,
            "X-DaedalMap-Artifact-Version": str(artifact.get("artifact_version") or ""),
            "X-DaedalMap-Sha256": str(artifact.get("sha256") or ""),
        }
        return Response(content=artifact_bytes, media_type=content_type or "application/gzip", headers=headers)
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=409)
    except FileNotFoundError as exc:
        logger.warning("Research browser source artifact missing: %s", exc)
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=404)
    except Exception as exc:
        logger.exception("Research browser source artifact error")
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@router.post("/api/research/browser-save/load-install-manifest")
async def research_load_browser_install_manifest_endpoint(req: Request):
    wants_msgpack = "application/msgpack" in str(req.headers.get("accept") or "").lower()
    try:
        body = await decode_json_or_msgpack_body(req)
        corpus_id = str(body.get("corpusId") or "").strip()
        source_snapshots = body.get("sourceSnapshots")
        source_artifacts = body.get("sourceArtifacts")
        if not corpus_id:
            payload = {"ok": False, "error": "No corpusId provided"}
            return msgpack_response(payload, status_code=400) if wants_msgpack else JSONResponse(payload, status_code=400)
        if isinstance(source_artifacts, list):
            source_snapshots = _decode_browser_source_artifact_payloads(source_artifacts)
        if not isinstance(source_snapshots, list):
            payload = {"ok": False, "error": "No sourceArtifacts or sourceSnapshots provided"}
            return msgpack_response(payload, status_code=400) if wants_msgpack else JSONResponse(payload, status_code=400)

        auth_user = await get_authenticated_user_async(req)
        user_id = (auth_user or {}).get("id")
        if not user_id:
            payload = {"ok": False, "error": "Authentication required"}
            return msgpack_response(payload, status_code=401) if wants_msgpack else JSONResponse(payload, status_code=401)

        frontend_session_id = str(body.get("sessionId") or f"browser-save:{corpus_id}").strip() or f"browser-save:{corpus_id}"
        session_id = build_session_cache_key(frontend_session_id, auth_user)
        saved_corpus = _load_saved_corpus_for_user(user_id, corpus_id)
        if not saved_corpus:
            payload = {"ok": False, "error": "Saved corpus not found"}
            return msgpack_response(payload, status_code=404) if wants_msgpack else JSONResponse(payload, status_code=404)

        manifest = _annotate_manifest_saved_corpus_state(
            _restore_browser_install_source_snapshots(
                session_id=session_id,
                saved_corpus=saved_corpus,
                source_snapshots=source_snapshots,
            )
        )
        saved_name = ((manifest.get("saved_corpus") or {}).get("name") or "Saved corpus")
        payload = _json_safe_value({
            "ok": True,
            "corpus": manifest,
            "message": f'Loaded "{saved_name}" into the Research workspace from browser-saved source artifacts.',
        })
        return msgpack_response(payload) if wants_msgpack else JSONResponse(payload)
    except ValueError as exc:
        payload = {"ok": False, "error": str(exc)}
        return msgpack_response(payload, status_code=409) if wants_msgpack else JSONResponse(payload, status_code=409)
    except Exception as exc:
        logger.exception("Research browser install-manifest restore error")
        payload = {"ok": False, "error": str(exc)}
        return msgpack_response(payload, status_code=500) if wants_msgpack else JSONResponse(payload, status_code=500)


@router.post("/chat/research")
async def research_chat_endpoint(req: Request):
    try:
        body = await decode_request_body(req)
        query = body.get("query", "")
        if not query:
            return msgpack_error("No query provided", 400)
        route_context, route_error, rejection_payload, rejection_status, rejection_headers = await prepare_research_chat_route_context(
            req,
            body,
            query=query,
            request_id_func=research_request_id,
        )
        if route_error:
            return route_error
        if rejection_payload is not None:
            log_conversation(
                route_context.frontend_session_id if route_context else body.get("sessionId", "anonymous"),
                query,
                rejection_payload.get("message", ""),
                surface="research",
                intent=rejection_payload.get("error_code") or "anonymous_budget_blocked",
                metadata=build_chat_gate_log_metadata(
                    rejection_payload,
                    gate_kind="anonymous_daily_budget",
                ),
            )
            return msgpack_response(
                rejection_payload,
                status_code=rejection_status or 400,
                headers=rejection_headers or {},
            )
        assert route_context is not None
        turn_limit_payload, turn_limit_status, turn_limit_headers = anonymous_turn_limit_rejection_payload(
            session_id=route_context.session_id,
            caller_ctx=route_context.caller_ctx,
            lane="research",
        )
        if turn_limit_payload is not None:
            log_conversation(
                route_context.frontend_session_id,
                query,
                turn_limit_payload.get("message", ""),
                surface="research",
                intent=turn_limit_payload.get("error_code") or "anonymous_turn_limit_reached",
                metadata=build_chat_gate_log_metadata(
                    turn_limit_payload,
                    gate_kind="anonymous_turn_limit",
                ),
            )
            return msgpack_response(
                turn_limit_payload,
                status_code=turn_limit_status or 429,
                headers=turn_limit_headers or {},
            )
        register_anonymous_chat_turn(
            session_id=route_context.session_id,
            caller_ctx=route_context.caller_ctx,
            lane="research",
        )
        usage_recorder, rescue_usage_recorder = build_usage_recorders(
            surface="research",
            call_kinds=("research_main", "research_rescue"),
            session_id=route_context.session_id,
            request_id=route_context.request_id,
            caller_ctx=route_context.caller_ctx,
            qa_suite_metadata=route_context.qa_suite_metadata,
        )
        try:
            result = await run_turn(
                session_id=route_context.session_id,
                query=query,
                chat_history=body.get("chatHistory", []),
                research_memory=body.get("researchMemory"),
                force_large_display=bool(body.get("force_research_display")),
                usage_recorder=usage_recorder,
                rescue_usage_recorder=rescue_usage_recorder,
                catalog_surface=route_context.catalog_surface,
            )
        finally:
            usage_recorder.flush()
            rescue_usage_recorder.flush(skip_if_empty=True)
        await settle_and_log_research_turn(
            route_context=route_context,
            query=query,
            result=result,
            user_agent=(req.headers.get("user-agent") or "")[:300] or None,
        )
        return msgpack_response(result)
    except Exception as exc:
        logger.exception("Research chat error")
        log_app_error(type(exc).__name__, str(exc), surface="human_app", path="/chat/research")
        return msgpack_response(
            build_provider_error_payload(
                exc,
                lane="research",
                request_id=getattr(getattr(req, "state", None), "analytics_request_id", None),
            )
            or build_chat_error_payload(
                lane="research",
                message="Research mode hit an internal error.",
                error_code="research_internal_error",
                request_id=getattr(getattr(req, "state", None), "analytics_request_id", None),
                stage="route",
                retry_hint="Retry the question. If it keeps failing, reload the corpus or narrow the request."
            ),
            status_code=500,
        )


@router.post("/chat/research/stream")
async def research_chat_stream_endpoint(req: Request):
    body = await decode_json_or_msgpack_body(req)

    async def generate_events():
        try:
            query = body.get("query", "")
            if not query:
                yield encode_sse(stage_payload("complete", result={"type": "error", "message": "No query provided"}))
                return
            route_context, route_error, rejection_payload, _rejection_status, _rejection_headers = await prepare_research_chat_route_context(
                req,
                body,
                query=query,
                request_id_func=research_request_id,
            )
            if route_error or rejection_payload is not None:
                payload = rejection_payload or {"type": "error", "message": "WIP catalog access is limited to admin accounts."}
                if rejection_payload is not None and route_context is not None:
                    log_conversation(
                        route_context.frontend_session_id,
                        query,
                        rejection_payload.get("message", ""),
                        surface="research",
                        intent=rejection_payload.get("error_code") or "anonymous_budget_blocked",
                        metadata=build_chat_gate_log_metadata(
                            rejection_payload,
                            gate_kind="anonymous_daily_budget",
                        ),
                    )
                yield encode_sse(stage_payload("complete", result=payload))
                return
            assert route_context is not None
            turn_limit_payload, _turn_limit_status, _turn_limit_headers = anonymous_turn_limit_rejection_payload(
                session_id=route_context.session_id,
                caller_ctx=route_context.caller_ctx,
                lane="research",
            )
            if turn_limit_payload is not None:
                log_conversation(
                    route_context.frontend_session_id,
                    query,
                    turn_limit_payload.get("message", ""),
                    surface="research",
                    intent=turn_limit_payload.get("error_code") or "anonymous_turn_limit_reached",
                    metadata=build_chat_gate_log_metadata(
                        turn_limit_payload,
                        gate_kind="anonymous_turn_limit",
                    ),
                )
                yield encode_sse(stage_payload("complete", result=turn_limit_payload))
                return
            register_anonymous_chat_turn(
                session_id=route_context.session_id,
                caller_ctx=route_context.caller_ctx,
                lane="research",
            )
            usage_recorder, rescue_usage_recorder = build_usage_recorders(
                surface="research",
                call_kinds=("research_main", "research_rescue"),
                session_id=route_context.session_id,
                request_id=route_context.request_id,
                caller_ctx=route_context.caller_ctx,
                qa_suite_metadata=route_context.qa_suite_metadata,
            )

            yield encode_sse(stage_payload("corpus", message="Reading Research workspace..."), dumps=json_dumps_safe)
            yield encode_sse(stage_payload("thinking", message="Researching loaded workspace data..."), dumps=json_dumps_safe)

            bus, task = await run_turn_with_progress(
                session_id=route_context.session_id,
                query=query,
                chat_history=body.get("chatHistory", []),
                research_memory=body.get("researchMemory"),
                force_large_display=bool(body.get("force_research_display")),
                usage_recorder=usage_recorder,
                rescue_usage_recorder=rescue_usage_recorder,
                catalog_surface=route_context.catalog_surface,
            )
            try:
                async for event in bus.drain_until(
                    task,
                    heartbeat_seconds=4.0,
                    heartbeat=progress_heartbeat,
                ):
                    yield encode_sse(progress_payload(event), dumps=json_dumps_safe)

                result = await task
            finally:
                usage_recorder.flush()
                rescue_usage_recorder.flush(skip_if_empty=True)
            await settle_and_log_research_turn(
                route_context=route_context,
                query=query,
                result=result,
                user_agent=(req.headers.get("user-agent") or "")[:300] or None,
            )
            yield encode_sse(stage_payload("writing", message="Writing research answer..."), dumps=json_dumps_safe)
            if result.get("type") == "chat" and result.get("message"):
                yield encode_sse(stage_payload("answer_start", message=""), dumps=json_dumps_safe)
                for chunk in _word_chunks(result.get("message", "")):
                    yield encode_sse(stage_payload("delta", text=chunk), dumps=json_dumps_safe)
                    await asyncio.sleep(0.035)
            yield encode_sse(stage_payload("complete", result=result), dumps=json_dumps_safe)
        except Exception as exc:
            logger.exception("Research chat stream error")
            log_app_error(type(exc).__name__, str(exc), surface="human_app", path="/chat/research/stream")
            error_result = build_chat_error_payload(
                lane="research",
                message="Research mode hit an internal error.",
                error_code="research_internal_error",
                request_id=getattr(getattr(req, "state", None), "analytics_request_id", None),
                stage="stream_route",
                retry_hint="Retry the question. If it keeps failing, reload the corpus or narrow the request."
            )
            provider_error = build_provider_error_payload(
                exc,
                lane="research",
                request_id=getattr(getattr(req, "state", None), "analytics_request_id", None),
                stage="llm_call",
            )
            if provider_error:
                error_result = provider_error
            yield encode_sse(stage_payload("complete", result=error_result), dumps=json_dumps_safe)

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
