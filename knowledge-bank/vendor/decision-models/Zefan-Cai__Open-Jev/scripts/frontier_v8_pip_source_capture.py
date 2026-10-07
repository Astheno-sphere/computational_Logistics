"""Bounded, read-only opaque installed-pip source capture; never imports pip.

Run only with the literal BOOTSTRAP below, via the declared interpreter and
``/usr/bin/env -i PIP_CONFIG_FILE=/dev/null ... -B -I -S -c BOOTSTRAP``.
The pure functions support fresh synthetic fixtures, not alternate host routes.
"""

import errno
import fcntl
import hashlib
import json
import math
import os
import re
import select
import stat
import sys
import time


SCHEMA_VERSION = 1
SCOPE = "frontier_v8_readonly_installed_pip_source_capture_CPU_fixture"
LOCK_SHA256 = "d1f238a916dfdfbc8b89f3de4c28bb3b7220cdd97ecf609ebb726afab0ca8221"
CAPS = {
    "observer_source_bytes": 524288,
    "request_bytes": 65536,
    "lock_bytes": 65536,
    "interpreter_file_bytes": 67108864,
    "site_entries_per_explicit_scan": 8192,
    "site_total_yielded_entries": 32768,
    "metadata_file_bytes": 262144,
    "metadata_total_per_snapshot": 2097152,
    "pip_tree_total_entries": 4096,
    "pip_tree_actual_yielded_entries": 8192,
    "pip_tree_depth": 16,
    "pip_tree_directories": 512,
    "selected_file_bytes": 2097152,
    "selected_source_total_bytes": 8388608,
    "simultaneously_owned_input_FDs": 24,
    "stdout_UTF8_bytes": 33554432,
    "work_seconds": 30,
    "self_total_seconds": 40,
}
AUTHORITY = dict.fromkeys((
    "GPU_or_foreign_restore", "containment_available", "execution_available",
    "functional_containment_verified", "model_runtime_ABI_observed",
    "production_controller_guard_completed", "resource_authority",
), False)
STAT_FIELDS = ("dev", "ino", "mode", "uid", "gid", "nlink", "size",
               "mtime_ns", "ctime_ns")
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
FILE_FLAGS = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC

# This independent bootstrap deliberately has no request-self-digest route.
# All path components are anchored before either mutable input is compiled.
BOOTSTRAP = r'''import hashlib, os, stat, sys
def stamp(s):
    return tuple(getattr(s, 'st_' + k) for k in ('dev','ino','mode','uid','gid','nlink','size','mtime_ns','ctime_ns'))
def parts(p):
    if not isinstance(p,str) or not p.startswith('/') or '\x00' in p:
        raise ValueError('absolute unambiguous input required')
    a=p.split('/')[1:]
    if not a or any(x in ('','.','..') for x in a):
        raise ValueError('ambiguous input component')
    return a
def capture(p, limit):
    a=parts(p); parent=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        for n in a[:-1]:
            before=os.stat(n,dir_fd=parent,follow_symlinks=False)
            child=os.open(n,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=parent)
            try:
                if not stat.S_ISDIR(before.st_mode) or stamp(before)!=stamp(os.fstat(child)) or stamp(before)!=stamp(os.stat(n,dir_fd=parent,follow_symlinks=False)):
                    raise ValueError('input directory drift')
            except BaseException:
                os.close(child); raise
            old=parent; parent=child; os.close(old)
        before=os.stat(a[-1],dir_fd=parent,follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode) or before.st_size>limit:
            raise ValueError('input type or declared size')
        fd=os.open(a[-1],os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=parent)
        try:
            opened=os.fstat(fd)
            if stamp(before)!=stamp(opened): raise ValueError('input open drift')
            body=bytearray()
            while True:
                b=os.read(fd,min(65536,limit-len(body)+1))
                if not b: break
                body.extend(b)
                if len(body)>limit: raise ValueError('actual input byte cap')
            after=os.fstat(fd)
            final=os.stat(a[-1],dir_fd=parent,follow_symlinks=False)
            if stamp(before)!=stamp(after) or stamp(before)!=stamp(final) or len(body)!=before.st_size:
                raise ValueError('input read drift')
            return bytes(body),stamp(before)
        finally: os.close(fd)
    finally: os.close(parent)
if len(sys.argv)!=6: raise ValueError('exact independent bootstrap argv required')
observer, observer_sha, request, request_sha, request_count=sys.argv[1:]
for h in (observer_sha,request_sha):
    if len(h)!=64 or any(c not in '0123456789abcdef' for c in h): raise ValueError('independent SHA required')
if not request_count.isascii() or not request_count.isdecimal() or str(int(request_count))!=request_count or not 0<int(request_count)<=65536:
    raise ValueError('independent exact request count required')
ob, ost=capture(observer,524288)
if hashlib.sha256(ob).hexdigest()!=observer_sha: raise ValueError('observer SHA mismatch')
rb, rst=capture(request,65536)
if len(rb)!=int(request_count) or hashlib.sha256(rb).hexdigest()!=request_sha: raise ValueError('independent request pin mismatch')
g={'__name__':'__main__','__file__':observer,'__captured_observer_bytes__':ob,'__captured_request_bytes__':rb,'__captured_inputs__':{'observer':ost,'request':rst},'__captured_original_argv__':list(sys.argv)}
exec(compile(ob,observer,'exec'),g,g)
'''


def observed_stat(value):
    """Comparable facts intentionally exclude atime."""
    return {key: getattr(value, "st_" + key) for key in STAT_FIELDS}


def _caps(overrides):
    result = dict(CAPS)
    if overrides is not None:
        if not isinstance(overrides, dict) or set(overrides) - set(CAPS):
            raise ValueError("unknown fixture cap")
        for key, value in overrides.items():
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0 or value > CAPS[key]:
                raise ValueError("fixture caps may only decrease")
            if key not in ("work_seconds", "self_total_seconds") and type(value) is not int:
                raise ValueError("integer cap required")
            result[key] = value
    return result


def _receipt():
    return {
        "schema_version": SCHEMA_VERSION, "scope": SCOPE, "status": "failed",
        "source_capture_complete": False, "source_capture_verified": False,
        "output_completion_claimed": False, "authority": dict(AUTHORITY),
        "dependency_consistency_verified": False, "pipcheck": 0,
        "completed_files": [], "current_file_partial": None,
        "metadata_snapshots": [], "error": None,
        "manifest": {
            "first_pass_unique_entries": 0, "actual_source_yielded_entries": 0,
            "source_scan_calls": 0,
            "traversed_directories": 1, "max_depth": 0, "site_scan_calls": 0,
            "site_scan_yielded_entries": [], "actual_site_yielded_entries": 0,
            "selected_source_bytes": 0, "peak_owned_input_FDs": 0,
            "selected_paths": [], "excluded_entries": [],
            "subset": ".py/.pyi opaque source only",
            "pycache_contents": "unobserved and unauthenticated; never traversed",
            "symlink_special_rejection": "actually enumerated entries only",
        },
    }


class CaptureError(Exception):
    def __init__(self, message, receipt=None):
        super().__init__(message)
        self.receipt = receipt


class _Capture:
    def __init__(self, caps=None, clock=time.monotonic, t0=None, receipt=None, pre_t0=False):
        self.caps = _caps(caps)
        self.clock = clock
        observed = clock() if t0 is None else t0
        self.t0 = None if pre_t0 else observed
        if not math.isfinite(observed):
            raise ValueError("nonfinite t0")
        self.last_clock = observed
        self.receipt = _receipt() if receipt is None else receipt
        self.stage = "prevalidation"
        self.failed = False
        self.owned = 0

    def check(self, total=False):
        if self.failed and not total:
            raise CaptureError("work already permanently failed", self.receipt)
        now = self.clock()
        if not math.isfinite(now) or now < self.last_clock:
            raise CaptureError("nonfinite or reverse monotonic clock", self.receipt)
        self.last_clock = now
        limit = "self_total_seconds" if total else "work_seconds"
        if self.t0 is not None and now >= self.t0 + self.caps[limit]:
            raise CaptureError(limit + " deadline", self.receipt)
        return now

    def lease(self):
        self.check()
        if self.owned >= self.caps["simultaneously_owned_input_FDs"]:
            raise CaptureError("owned input FD cap", self.receipt)
        self.owned += 1
        manifest = self.receipt["manifest"]
        manifest["peak_owned_input_FDs"] = max(manifest["peak_owned_input_FDs"], self.owned)

    def close(self, fd):
        # Once-close only: never retry an unknown close result.
        try:
            os.close(fd)
        finally:
            self.owned -= 1

    def open(self, name, flags, parent=None):
        self.lease()
        try:
            fd = os.open(name, flags, dir_fd=parent)
        except BaseException:
            self.owned -= 1
            raise
        try:
            self.check()
        except BaseException:
            self.close(fd)
            raise
        return fd

    def fail(self, error):
        self.failed = True
        self.receipt.update(status="failed", source_capture_complete=False)
        self.receipt["error"] = {
            "stage": self.stage, "type": type(error).__name__,
            "message": str(error)[:1024],
        }
        return CaptureError(str(error)[:1024], self.receipt)


def _parts(path):
    if not isinstance(path, str) or not path.startswith("/") or "\x00" in path:
        raise CaptureError("absolute unambiguous path required")
    parts = path.split("/")[1:]
    if not parts or any(p in ("", ".", "..") for p in parts):
        raise CaptureError("ambiguous path component")
    return parts


def _name(name):
    if not isinstance(name, str) or not name.isascii() or name.startswith(".") or name in ("", ".", "..") or "/" in name or "\x00" in name:
        raise CaptureError("dot/nonASCII/escaped source or site name")
    return name


def _entry(ctx, parent, name):
    ctx.check()
    value = os.stat(name, dir_fd=parent, follow_symlinks=False)
    ctx.check()
    return observed_stat(value)


def _directory(ctx, path):
    parts = _parts(path)
    fd = ctx.open("/", DIR_FLAGS)
    try:
        for name in parts:
            before = _entry(ctx, fd, name)
            child = ctx.open(name, DIR_FLAGS, fd)
            try:
                ctx.check()
                opened = observed_stat(os.fstat(child))
                ctx.check()
                if not stat.S_ISDIR(before["mode"]) or before != opened or before != _entry(ctx, fd, name):
                    raise CaptureError("anchored directory observed drift", ctx.receipt)
            except BaseException:
                ctx.close(child)
                raise
            old = fd
            fd = child
            ctx.close(old)
        return fd
    except BaseException:
        ctx.close(fd)
        raise


def _scan(ctx, fd, site=False, first=False):
    ctx.check()
    before = observed_stat(os.fstat(fd))
    ctx.check()
    manifest = ctx.receipt["manifest"]
    if site:
        manifest["site_scan_calls"] += 1
        manifest["site_scan_yielded_entries"].append(0)
        index = len(manifest["site_scan_yielded_entries"]) - 1
    else:
        index = None
        manifest["source_scan_calls"] += 1
    names = {}
    ctx.lease()  # os.scandir(fd) owns a duplicate descriptor until close.
    iterator = None
    try:
        iterator = os.scandir(fd)
        ctx.check()
        while True:
            ctx.check()
            try:
                item = next(iterator)
            except StopIteration:
                ctx.check()
                break
            # Charge immediately, even ignored children and the cap+1 yield.
            if site:
                manifest["site_scan_yielded_entries"][index] += 1
                manifest["actual_site_yielded_entries"] += 1
                if manifest["site_scan_yielded_entries"][index] > ctx.caps["site_entries_per_explicit_scan"] or manifest["actual_site_yielded_entries"] > ctx.caps["site_total_yielded_entries"]:
                    raise CaptureError("site actual yielded entry cap", ctx.receipt)
            else:
                manifest["actual_source_yielded_entries"] += 1
                if first:
                    manifest["first_pass_unique_entries"] += 1
                if manifest["actual_source_yielded_entries"] > ctx.caps["pip_tree_actual_yielded_entries"] or manifest["first_pass_unique_entries"] > ctx.caps["pip_tree_total_entries"]:
                    raise CaptureError("source actual/unique yielded entry cap", ctx.receipt)
            ctx.check()
            name = _name(item.name)
            if name in names:
                raise CaptureError("duplicate enumerated name", ctx.receipt)
            value = _entry(ctx, fd, name)
            if not (stat.S_ISDIR(value["mode"]) or stat.S_ISREG(value["mode"])):
                raise CaptureError("enumerated symlink or special entry", ctx.receipt)
            names[name] = value
    finally:
        try:
            if iterator is not None:
                iterator.close()
        finally:
            ctx.owned -= 1
    ctx.check()
    after = observed_stat(os.fstat(fd))
    ctx.check()
    if before != after:
        raise CaptureError("directory drift during bounded scan", ctx.receipt)
    return dict(sorted(names.items())), before


def _read_file(ctx, parent, name, limit, *, relative=None, expected=None):
    before = _entry(ctx, parent, name)
    if not stat.S_ISREG(before["mode"]) or before["size"] > limit:
        raise CaptureError("regular file declared byte cap/type", ctx.receipt)
    if expected is not None and before != expected:
        raise CaptureError("file entry observed drift", ctx.receipt)
    fd = ctx.open(name, FILE_FLAGS, parent)
    body = bytearray()
    partial = None
    try:
        ctx.check()
        opened = observed_stat(os.fstat(fd))
        ctx.check()
        if before != opened:
            raise CaptureError("file open observed drift", ctx.receipt)
        while True:
            ctx.check()
            chunk = os.read(fd, min(65536, limit - len(body) + 1))
            if chunk:
                body.extend(chunk)
                if relative is not None:
                    if partial is None:
                        partial = {"path": relative, "complete": False, "partial": True,
                                   "before_stat": before, "opened_stat": opened}
                        ctx.receipt["current_file_partial"] = partial
                    # Keep only the actual current body; finalize hash/hex once.
                    partial["_body"] = body
                if len(body) > limit:
                    raise CaptureError("actual file byte cap", ctx.receipt)
            ctx.check()
            if not chunk:
                break
        post = observed_stat(os.fstat(fd))
        if partial is not None:
            partial["post_stat"] = post
        ctx.check()
        final = _entry(ctx, parent, name)
        if partial is not None:
            partial["final_entry_stat"] = final
        if before != post or before != final or len(body) != before["size"]:
            raise CaptureError("file read observed drift/count", ctx.receipt)
        result = {"byte_count": len(body), "sha256": hashlib.sha256(body).hexdigest(),
                  "observed_stat": before}
        if relative is not None:
            result.update(path=relative, raw_hex=body.hex(), complete=True, partial=False)
        return bytes(body), result
    finally:
        ctx.close(fd)


def _finish_partial(receipt):
    partial = receipt["current_file_partial"]
    if partial is not None and "_body" in partial:
        body = partial.pop("_body")
        partial.update(byte_count=len(body), sha256=hashlib.sha256(body).hexdigest(), raw_hex=body.hex())


def _normalize(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_lock(data, *, expected_sha256=LOCK_SHA256):
    if not isinstance(data, bytes) or len(data) > CAPS["lock_bytes"] or hashlib.sha256(data).hexdigest() != expected_sha256:
        raise CaptureError("frozen lock byte/hash mismatch")
    result = {}
    for line in data.decode("ascii").splitlines():
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*==[^\s=]+", line):
            raise CaptureError("exact version-only lock required")
        name, version = line.split("==")
        name = _normalize(name)
        if name in result:
            raise CaptureError("duplicate normalized lock name")
        result[name] = version
    if len(result) != 76 or result.get("pip") != "24.0":
        raise CaptureError("exact frozen76 with pip24.0 required")
    return result


def _metadata_identity(body):
    fields = {}
    previous_identity = False
    for line in body.splitlines():
        if not line:
            break
        if line.startswith((b" ", b"\t")):
            if previous_identity:
                raise CaptureError("continued METADATA Name or Version")
            continue
        previous_identity = False
        for key in (b"Name", b"Version"):
            if line.lower().startswith(key.lower() + b":"):
                value = line.split(b":", 1)[1].strip().decode("ascii")
                if key in fields or not value or any(c.isspace() for c in value):
                    raise CaptureError("duplicate/invalid METADATA Name or Version")
                fields[key] = value
                previous_identity = True
    if set(fields) != {b"Name", b"Version"} or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", fields[b"Name"]):
        raise CaptureError("missing/escaped METADATA identity")
    return _normalize(fields[b"Name"]), fields[b"Version"]


def _metadata_snapshot(ctx, site_fd, site_path, expected_versions):
    ctx.stage = "metadata_snapshot"
    before, site_stat = _scan(ctx, site_fd, site=True)
    progress = {"complete": False, "distributions": [], "byte_count": 0}
    ctx.receipt.setdefault("metadata_progress", []).append(progress)
    observed = {}
    for name, entry_stat in before.items():
        if not name.endswith(".dist-info"):
            continue
        if not stat.S_ISDIR(entry_stat["mode"]):
            raise CaptureError("dist-info must be ordinary directory", ctx.receipt)
        fd = ctx.open(name, DIR_FLAGS, site_fd)
        try:
            ctx.check()
            if observed_stat(os.fstat(fd)) != entry_stat:
                raise CaptureError("metadata directory open drift", ctx.receipt)
            ctx.check()
            limit = min(ctx.caps["metadata_file_bytes"],
                        ctx.caps["metadata_total_per_snapshot"] - progress["byte_count"])
            body, facts = _read_file(ctx, fd, "METADATA", limit)
            progress["byte_count"] += len(body)
            normalized, version = _metadata_identity(body)
            if normalized in observed or normalized not in expected_versions or expected_versions[normalized] != version:
                raise CaptureError("extra/duplicate/version-drift metadata", ctx.receipt)
            facts.update(name=normalized, version=version,
                         path=site_path + "/" + name + "/METADATA")
            observed[normalized] = facts
            progress["distributions"].append(facts)
            ctx.check()
            if observed_stat(os.fstat(fd)) != entry_stat or _entry(ctx, site_fd, name) != entry_stat:
                raise CaptureError("metadata directory postread drift", ctx.receipt)
        finally:
            ctx.close(fd)
    if set(observed) != set(expected_versions) or len(observed) != 76:
        raise CaptureError("missing frozen76 metadata", ctx.receipt)
    after, after_stat = _scan(ctx, site_fd, site=True)
    if before != after or site_stat != after_stat:
        raise CaptureError("site name/stat drift", ctx.receipt)
    progress["complete"] = True
    snapshot = {"distributions": [observed[n] for n in sorted(observed)],
                "site_names": sorted(before), "site_stat": site_stat}
    ctx.receipt["metadata_snapshots"].append(snapshot)
    return snapshot


def _source_directory(ctx, fd, relative, depth, device):
    ctx.stage = "source_traversal"
    ctx.check()
    if depth > ctx.caps["pip_tree_depth"]:
        raise CaptureError("pip directory depth cap", ctx.receipt)
    if ctx.receipt["manifest"]["traversed_directories"] > ctx.caps["pip_tree_directories"]:
        raise CaptureError("pip directory count cap", ctx.receipt)
    before, directory_stat = _scan(ctx, fd, first=True)
    if directory_stat["dev"] != device:
        raise CaptureError("cross-device source directory", ctx.receipt)
    manifest = ctx.receipt["manifest"]
    manifest.setdefault("directories", []).append({
        "path": relative, "depth": depth, "observed_stat": directory_stat,
    })
    manifest["max_depth"] = max(manifest["max_depth"], depth)
    for name, entry_stat in before.items():
        path = name if not relative else relative + "/" + name
        if entry_stat["dev"] != device:
            raise CaptureError("cross-device source entry", ctx.receipt)
        if stat.S_ISDIR(entry_stat["mode"]):
            if name == "__pycache__":
                manifest["excluded_entries"].append({
                    "path": path, "kind": "directory", "reason": "pycache_contents_unobserved",
                    "observed_stat": entry_stat,
                })
                continue
            manifest["traversed_directories"] += 1
            if manifest["traversed_directories"] > ctx.caps["pip_tree_directories"] or depth + 1 > ctx.caps["pip_tree_depth"]:
                raise CaptureError("pip directory count/depth cap", ctx.receipt)
            child = ctx.open(name, DIR_FLAGS, fd)
            try:
                ctx.check()
                if observed_stat(os.fstat(child)) != entry_stat:
                    raise CaptureError("source directory open drift", ctx.receipt)
                ctx.check()
                _source_directory(ctx, child, path, depth + 1, device)
                ctx.check()
                if observed_stat(os.fstat(child)) != entry_stat or _entry(ctx, fd, name) != entry_stat:
                    raise CaptureError("source directory postcapture drift", ctx.receipt)
            finally:
                ctx.close(child)
        elif name.endswith((".py", ".pyi")):
            ctx.stage = "source_file:" + path
            limit = min(ctx.caps["selected_file_bytes"],
                        ctx.caps["selected_source_total_bytes"] - manifest["selected_source_bytes"])
            _, facts = _read_file(ctx, fd, name, limit, relative=path, expected=entry_stat)
            ctx.receipt["completed_files"].append(facts)
            ctx.receipt["current_file_partial"] = None
            manifest["selected_paths"].append(path)
            manifest["selected_source_bytes"] += facts["byte_count"]
            ctx.check()
        else:
            manifest["excluded_entries"].append({
                "path": path, "kind": "regular_file", "reason": "not_py_or_pyi",
                "observed_stat": entry_stat,
            })
    ctx.stage = "source_traversal_postcheck"
    after, after_stat = _scan(ctx, fd)
    if before != after or directory_stat != after_stat:
        raise CaptureError("source directory name/stat drift", ctx.receipt)


def _capture_site(ctx, site_path, expected_versions):
    if not isinstance(expected_versions, dict) or len(expected_versions) != 76 or expected_versions.get("pip") != "24.0":
        raise CaptureError("exact frozen76 metadata expectations required", ctx.receipt)
    ctx.stage = "site_open"
    site_fd = _directory(ctx, site_path)
    try:
        first = _metadata_snapshot(ctx, site_fd, site_path, expected_versions)
        pip_stat = _entry(ctx, site_fd, "pip")
        if not stat.S_ISDIR(pip_stat["mode"]):
            raise CaptureError("ordinary pip root directory required", ctx.receipt)
        pip_fd = ctx.open("pip", DIR_FLAGS, site_fd)
        try:
            ctx.check()
            if observed_stat(os.fstat(pip_fd)) != pip_stat or pip_stat["dev"] != first["site_stat"]["dev"]:
                raise CaptureError("pip root identity/device mismatch", ctx.receipt)
            ctx.check()
            _source_directory(ctx, pip_fd, "", 0, pip_stat["dev"])
            ctx.check()
            if observed_stat(os.fstat(pip_fd)) != pip_stat or _entry(ctx, site_fd, "pip") != pip_stat:
                raise CaptureError("pip root postcapture drift", ctx.receipt)
        finally:
            ctx.close(pip_fd)
        manifest = ctx.receipt["manifest"]
        required = {"__init__.py", "__main__.py", "_internal/commands/check.py"}
        directories = {item["path"] for item in manifest["directories"]}
        if not required.issubset(manifest["selected_paths"]) or "_vendor" not in directories:
            raise CaptureError("required pip source paths missing", ctx.receipt)
        second = _metadata_snapshot(ctx, site_fd, site_path, expected_versions)
        if first != second:
            raise CaptureError("fresh metadata snapshot drift", ctx.receipt)
        ctx.receipt["completed_files"].sort(key=lambda item: item["path"].encode("ascii"))
        manifest["selected_paths"].sort(key=lambda name: name.encode("ascii"))
        manifest["excluded_entries"].sort(key=lambda item: item["path"].encode("ascii"))
        manifest["directories"].sort(key=lambda item: item["path"].encode("ascii"))
        ctx.check()
    finally:
        ctx.close(site_fd)


def capture_site(site_path, expected_versions, *, caps=None, clock=time.monotonic):
    """Capture a fresh synthetic site; CLI adds separate host/input bindings."""
    receipt = _receipt()
    ctx = None
    try:
        ctx = _Capture(caps, clock, receipt=receipt)
        _capture_site(ctx, site_path, expected_versions)
        ctx.check()
        ctx.receipt.update(status="source_capture_candidate_ready", source_capture_complete=True)
        return ctx.receipt
    except Exception as error:
        if ctx is None:
            receipt["error"] = {"stage": "clock_or_caps_initialization", "type": type(error).__name__,
                                "message": str(error)[:1024]}
            raise CaptureError(str(error)[:1024], receipt) from error
        _finish_partial(receipt)
        raise ctx.fail(error) from error


def prepare_stdout(fd, *, declared=None):
    """Set/observe nonblocking on the assumed exclusive inherited FIFO only."""
    if declared is not None and declared != {"kind": "private_FIFO", "exclusive_channel_assumption": True}:
        raise CaptureError("declared private FIFO assumption required")
    value = observed_stat(os.fstat(fd))
    if not stat.S_ISFIFO(value["mode"]):
        raise CaptureError("stdout must be private caller FIFO")
    before = fcntl.fcntl(fd, fcntl.F_GETFL)
    changed = not bool(before & os.O_NONBLOCK)
    if changed:
        fcntl.fcntl(fd, fcntl.F_SETFL, before | os.O_NONBLOCK)
    after = fcntl.fcntl(fd, fcntl.F_GETFL)
    if not after & os.O_NONBLOCK:
        raise CaptureError("stdout O_NONBLOCK not observed")
    return {"kind": "FIFO", "exclusive_channel_assumption": True,
            "observed_stat": value, "flags_before": before, "flags_after": after,
            "set_nonblocking": changed, "nonblocking_verified": True}


def emit_json(receipt, fd, *, caps=None, clock=time.monotonic, t0=None):
    """Emit once; advancing cursor uses only actual positive write returns.

    Returned local facts cannot be part of the already serialized payload.
    A failed/partial stream is never repaired or retried as another JSON.
    """
    ctx = _Capture(caps, clock, t0=t0)
    ctx.check(total=True)
    prepare_stdout(fd)
    ctx.check(total=True)
    payload = (json.dumps(receipt, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False) + "\n").encode("utf-8")
    ctx.check(total=True)
    if len(payload) > ctx.caps["stdout_UTF8_bytes"]:
        raise CaptureError("serialized stdout UTF8 byte cap")
    facts = {"byte_count": len(payload), "sha256": hashlib.sha256(payload).hexdigest(),
             "write_calls": 0, "positive_returned_bytes": 0, "eagain_count": 0,
             "ready_waits": 0}
    cursor = 0
    while cursor < len(payload):
        now = ctx.check(total=True)
        facts["write_calls"] += 1
        try:
            written = os.write(fd, memoryview(payload)[cursor:cursor + 65536])
        except BlockingIOError as error:
            if error.errno not in (errno.EAGAIN, errno.EWOULDBLOCK):
                raise
            facts["eagain_count"] += 1
            now = ctx.check(total=True)
            facts["ready_waits"] += 1
            select.select([], [fd], [], min(0.05, ctx.t0 + ctx.caps["self_total_seconds"] - now))
            ctx.check(total=True)
            continue
        if type(written) is not int or written <= 0 or written > min(65536, len(payload) - cursor):
            raise CaptureError("invalid/zero stdout write result")
        cursor += written
        facts["positive_returned_bytes"] += written
        ctx.check(total=True)
    return facts


def _absolute_read(ctx, path, limit):
    parts = _parts(path)
    parent = _directory(ctx, "/" + "/".join(parts[:-1])) if len(parts) > 1 else ctx.open("/", DIR_FLAGS)
    try:
        body, facts = _read_file(ctx, parent, parts[-1], limit)
        facts["path"] = path
        return body, facts
    finally:
        ctx.close(parent)


def _postvalidate(ctx, path, expected):
    parts = _parts(path)
    parent = _directory(ctx, "/" + "/".join(parts[:-1])) if len(parts) > 1 else ctx.open("/", DIR_FLAGS)
    try:
        before = _entry(ctx, parent, parts[-1])
        if before != expected or not stat.S_ISREG(before["mode"]):
            raise CaptureError("input postvalidation entry drift", ctx.receipt)
        fd = ctx.open(parts[-1], FILE_FLAGS, parent)
        try:
            ctx.check()
            value = observed_stat(os.fstat(fd))
            ctx.check()
            if value != expected or _entry(ctx, parent, parts[-1]) != expected:
                raise CaptureError("input postvalidation open drift", ctx.receipt)
        finally:
            ctx.close(fd)
    finally:
        ctx.close(parent)


def _postvalidate_directory(ctx, path, expected):
    fd = _directory(ctx, path)
    try:
        ctx.check()
        value = observed_stat(os.fstat(fd))
        ctx.check()
        if value != expected:
            raise CaptureError("anchored directory postvalidation drift", ctx.receipt)
    finally:
        ctx.close(fd)


def _proc_read(ctx, path, limit=65536):
    """Explicit proc identity observations; proc virtual sizes are descriptive."""
    parts = _parts(path)
    parent = _directory(ctx, "/" + "/".join(parts[:-1]))
    try:
        fd = ctx.open(parts[-1], FILE_FLAGS, parent)
        body = bytearray()
        try:
            while True:
                ctx.check()
                chunk = os.read(fd, min(4096, limit - len(body) + 1))
                body.extend(chunk)
                ctx.check()
                if len(body) > limit:
                    raise CaptureError("proc identity actual byte cap", ctx.receipt)
                if not chunk:
                    return bytes(body)
        finally:
            ctx.close(fd)
    finally:
        ctx.close(parent)


def _self_identity(ctx):
    pid = os.getpid()
    ctx.check()
    data = _proc_read(ctx, "/proc/" + str(pid) + "/stat").decode("ascii")
    end = data.rfind(") ")
    fields = data[end + 2:].split()
    if end < 0 or int(data.split(" ", 1)[0]) != pid or len(fields) < 20:
        raise CaptureError("actual self proc identity invalid", ctx.receipt)
    boot_id = _proc_read(ctx, "/proc/sys/kernel/random/boot_id", 128).decode("ascii").strip()
    if not re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", boot_id):
        raise CaptureError("actual boot identity invalid", ctx.receipt)
    command = _proc_read(ctx, "/proc/" + str(pid) + "/cmdline")
    if not command.endswith(b"\x00"):
        raise CaptureError("actual proc argv invalid", ctx.receipt)
    ctx.check()
    executable = os.readlink("/proc/self/exe")
    ctx.check()
    _parts(executable)
    return {"pid": pid, "birth_ticks": int(fields[19]), "ppid": int(fields[1]),
            "boot_id": boot_id, "uid": os.getuid(), "effective_uid": os.geteuid(),
            "hostname": os.uname().nodename, "proc_self_exe_target": executable,
            "sys_executable_descriptive": sys.executable,
            "proc_argv": [item.decode("utf-8", "surrogateescape") for item in command[:-1].split(b"\x00")]}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CaptureError("duplicate request JSON key")
        result[key] = value
    return result


def _strict_request(body):
    def reject_constant(value):
        raise CaptureError("nonfinite request JSON constant: " + value)
    request = json.loads(body.decode("utf-8"), object_pairs_hook=_unique_object,
                         parse_constant=reject_constant)
    keys = {"schema_version", "scope", "case", "nonce", "attempt", "root",
            "observer_path", "observer_sha256", "request_path", "lock_path",
            "lock_sha256", "site_path", "host", "runtime", "stdout"}
    if not isinstance(request, dict) or set(request) != keys:
        raise CaptureError("exact new request keys required")
    if type(request["schema_version"]) is not int or request["schema_version"] != 1 or request["scope"] != SCOPE or request["case"] != "source_capture" or request["attempt"] != "attempt-r1":
        raise CaptureError("new schema/scope/case/attempt mismatch")
    if not isinstance(request["nonce"], str) or not re.fullmatch(r"[0-9a-f]{64}", request["nonce"]):
        raise CaptureError("fresh64hex nonce required")
    root = request["root"]
    for key in ("root", "observer_path", "request_path", "lock_path", "site_path"):
        _parts(request[key])
    expected_paths = {"observer_path": root + "/frontier_v8_pip_source_capture.py",
                      "request_path": root + "/source-capture-request.json",
                      "lock_path": root + "/requirements-linux-py311-cu128-20261002.lock"}
    if any(request[key] != path for key, path in expected_paths.items()) or request["lock_sha256"] != LOCK_SHA256:
        raise CaptureError("exact new source/request/lock paths and lock pin required")
    if not isinstance(request["observer_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", request["observer_sha256"]):
        raise CaptureError("observer SHA declaration required")
    site = request["site_path"]
    if site == root or site.startswith(root + "/") or root.startswith(site + "/"):
        raise CaptureError("readonly site and fresh writable root must be disjoint")
    host = request["host"]
    runtime = request["runtime"]
    if not isinstance(host, dict) or set(host) != {"hostname", "boot_id", "uid"} or type(host["uid"]) is not int or host["uid"] < 0 or not isinstance(host["hostname"], str) or not isinstance(host["boot_id"], str):
        raise CaptureError("exact declared host identity required")
    if not isinstance(runtime, dict) or set(runtime) != {"interpreter_path", "byte_count", "sha256"}:
        raise CaptureError("exact declared interpreter identity required")
    _parts(runtime["interpreter_path"])
    if type(runtime["byte_count"]) is not int or not 0 < runtime["byte_count"] <= CAPS["interpreter_file_bytes"] or not isinstance(runtime["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", runtime["sha256"]):
        raise CaptureError("interpreter full count/hash required")
    if request["stdout"] != {"kind": "private_FIFO", "exclusive_channel_assumption": True}:
        raise CaptureError("private FIFO exclusive-channel assumption required")
    return request


def _runtime_check(ctx, site_path):
    ctx.check()
    if sys.platform != "linux" or not all((sys.flags.dont_write_bytecode,
                                          sys.flags.isolated, sys.flags.no_site,
                                          sys.flags.ignore_environment)):
        raise CaptureError("Linux -B -I -S isolated interpreter required", ctx.receipt)
    if os.environ.get("PIP_CONFIG_FILE") != "/dev/null" or set(os.environ) - {"PIP_CONFIG_FILE", "LC_CTYPE"}:
        raise CaptureError("env -i PIP_CONFIG_FILE=/dev/null required", ctx.receipt)
    # CPython may create LC_CTYPE itself during pre-bootstrap locale coercion.
    if "LC_CTYPE" in os.environ and os.environ["LC_CTYPE"] not in ("C.UTF-8", "C.utf8", "UTF-8"):
        raise CaptureError("unexpected startup locale environment", ctx.receipt)
    forbidden = ("pip", "torch", "transformers", "peft", "triton", "safetensors", "accelerate")
    if any(name == prefix or name.startswith(prefix + ".")
           for name in sys.modules for prefix in forbidden):
        raise CaptureError("pip/vendor or forbidden runtime module present", ctx.receipt)
    if any(path == site_path or path.startswith(site_path + "/") for path in sys.path):
        raise CaptureError("installed site present in sys.path", ctx.receipt)
    ctx.check()


def _marker(ctx, root_fd, request):
    ctx.stage = "fresh_attempt_marker"
    ctx.check(total=True)
    marker = {"schema_version": 1, "scope": SCOPE, "case": "source_capture",
              "nonce": request["nonce"], "attempt": "attempt-r1",
              "t0_monotonic": ctx.t0, "status": "attempt_consumed",
              "source_capture_verified": False, "output_completion_claimed": False}
    body = (json.dumps(marker, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("ascii")
    # Only this new marker is written. Its regular fd is a local output lease.
    fd = os.open("attempt-r1.marker.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                 os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=root_fd)
    try:
        ctx.check(total=True)
        cursor = 0
        calls = 0
        while cursor < len(body):
            ctx.check(total=True)
            returned = os.write(fd, body[cursor:])
            calls += 1
            if type(returned) is not int or returned <= 0 or returned > len(body) - cursor:
                raise CaptureError("marker invalid write result", ctx.receipt)
            cursor += returned
            ctx.check(total=True)
        os.fsync(fd)
        ctx.check(total=True)
        facts = {"path": request["root"] + "/attempt-r1.marker.json",
                 "exclusive_create_returned": True, "write_calls": calls,
                 "positive_returned_bytes": cursor, "fsync_returned": True,
                 "durability_verified": False}
    finally:
        os.close(fd)
    return facts


def main():
    """No alternate direct-file/argument route; failed attempts stay consumed."""
    receipt = _receipt()
    ctx = _Capture(receipt=receipt, pre_t0=True)
    root_fd = None
    try:
        ctx.stage = "bootstrap_binding"
        required = ("__captured_observer_bytes__", "__captured_request_bytes__",
                    "__captured_inputs__", "__captured_original_argv__")
        if any(key not in globals() for key in required):
            raise CaptureError("literal reviewed bootstrap captured globals required", receipt)
        observer = globals()[required[0]]
        request_body = globals()[required[1]]
        original_argv = globals()[required[3]]
        if original_argv != sys.argv or len(original_argv) != 6:
            raise CaptureError("original bootstrap argv drift", receipt)
        observer_path, observer_sha, request_path, request_sha, request_count = original_argv[1:]
        if type(observer) is not bytes or type(request_body) is not bytes or len(observer) > CAPS["observer_source_bytes"] or len(request_body) > CAPS["request_bytes"] or hashlib.sha256(observer).hexdigest() != observer_sha or hashlib.sha256(request_body).hexdigest() != request_sha or str(len(request_body)) != request_count:
            raise CaptureError("independently bound captured inputs mismatch", receipt)
        captured_stats = globals()[required[2]]
        if not isinstance(captured_stats, dict) or set(captured_stats) != {"observer", "request"}:
            raise CaptureError("explicit captured stat globals required", receipt)
        input_stats = {}
        for key in ("observer", "request"):
            values = captured_stats[key]
            if not isinstance(values, tuple) or len(values) != len(STAT_FIELDS) or any(type(v) is not int for v in values):
                raise CaptureError("captured input stat tuple invalid", receipt)
            input_stats[key] = dict(zip(STAT_FIELDS, values))
        ctx.stage = "request_prevalidation"
        request = _strict_request(request_body)
        if request["observer_path"] != observer_path or request["observer_sha256"] != observer_sha or request["request_path"] != request_path:
            raise CaptureError("request source/path binding mismatch", receipt)
        receipt.update(case=request["case"], nonce=request["nonce"], attempt=request["attempt"])
        receipt["bootstrap"] = {"observer_sha256": observer_sha,
                                "observer_byte_count": len(observer),
                                "request_sha256_independent": request_sha,
                                "request_byte_count_independent": len(request_body),
                                "original_sys_argv": original_argv,
                                "same_captured_observer_bytes_executed": True}
        _runtime_check(ctx, request["site_path"])
        ctx.stage = "source_request_lock_interpreter_prevalidation"
        _postvalidate(ctx, observer_path, input_stats["observer"])
        _postvalidate(ctx, request_path, input_stats["request"])
        lock_body, lock_facts = _absolute_read(ctx, request["lock_path"], CAPS["lock_bytes"])
        expected_versions = parse_lock(lock_body)
        identity = _self_identity(ctx)
        host = request["host"]
        if any(identity[k] != host[k] for k in ("hostname", "boot_id", "uid")) or identity["effective_uid"] != host["uid"] or identity["ppid"] != os.getppid():
            raise CaptureError("fresh actual host/self identity mismatch", receipt)
        runtime = request["runtime"]
        if identity["proc_self_exe_target"] != runtime["interpreter_path"]:
            raise CaptureError("actual canonical interpreter target mismatch", receipt)
        expected_proc_argv = [runtime["interpreter_path"], "-B", "-I", "-S", "-c", BOOTSTRAP] + original_argv[1:]
        if identity["proc_argv"] != expected_proc_argv:
            raise CaptureError("literal actual interpreter/bootstrap argv mismatch", receipt)
        _, interpreter = _absolute_read(ctx, runtime["interpreter_path"], CAPS["interpreter_file_bytes"])
        if interpreter["byte_count"] != runtime["byte_count"] or interpreter["sha256"] != runtime["sha256"]:
            raise CaptureError("full actual interpreter file mismatch", receipt)
        root_fd = _directory(ctx, request["root"])
        ctx.check()
        root_stat = observed_stat(os.fstat(root_fd))
        ctx.check()
        if root_stat["uid"] != host["uid"] or stat.S_IMODE(root_stat["mode"]) != 0o700:
            raise CaptureError("fresh private caller root owner/mode required", receipt)
        receipt["stdout"] = prepare_stdout(1, declared=request["stdout"])
        receipt["inputs"] = {
            "observer": {"path": observer_path, "byte_count": len(observer), "sha256": observer_sha, "observed_stat": input_stats["observer"]},
            "request": {"path": request_path, "byte_count": len(request_body), "sha256": request_sha, "observed_stat": input_stats["request"]},
            "lock": lock_facts, "site_path": request["site_path"],
        }
        receipt["interpreter"] = interpreter
        receipt["self_identity"] = identity
        receipt["stdlib_origins_descriptive"] = {
            name: getattr(module, "__file__", None)
            for name, module in sorted(sys.modules.items())
            if name in ("os", "stat", "json", "hashlib", "fcntl", "select", "time", "re")
        }
        receipt["limitations"] = [
            "Pre-t0 interpreter/loader/stdlib/bootstrap/input startup is excluded from work30/total40.",
            "Filesystem and stdlib calls can block beyond cooperative before/after deadlines.",
            "Non-atomic name/stat/byte checks do not prevent privileged restores or all filesystem races.",
            "FD accounting covers controlled own input handles and conservative iterator leases, not all interpreter handles.",
            "Interpreter/proc/stdlib facts describe trusted baseline, not loaded/mapped code, ABI or containment.",
            "Only .py/.pyi bodies are captured; excluded pycache contents are unobserved and unauthenticated.",
            "Private stdout exclusivity is a caller assumption; flags alter its inherited open-file description.",
            "CPython can add LC_CTYPE during pre-bootstrap locale coercion after env -i.",
            "A candidate cannot certify its later emission, remote receipt durability, cleanup or dependency consistency.",
        ]
        # This is the one work/total t0, after bounded input prevalidation.
        ctx.check()
        ctx.t0 = ctx.clock()
        if not math.isfinite(ctx.t0) or ctx.t0 < ctx.last_clock:
            raise CaptureError("invalid actual t0", receipt)
        ctx.last_clock = ctx.t0
        receipt["deadlines"] = {"t0_monotonic": ctx.t0,
                                "work_deadline": ctx.t0 + CAPS["work_seconds"],
                                "total_deadline": ctx.t0 + CAPS["self_total_seconds"],
                                "pre_t0_startup_excluded": True}
        receipt["marker"] = _marker(ctx, root_fd, request)
        ctx.check()
        _capture_site(ctx, request["site_path"], expected_versions)
        ctx.stage = "input_self_postvalidation"
        for path, expected in ((observer_path, input_stats["observer"]),
                               (request_path, input_stats["request"]),
                               (request["lock_path"], lock_facts["observed_stat"]),
                               (runtime["interpreter_path"], interpreter["observed_stat"])):
            _postvalidate(ctx, path, expected)
        _postvalidate_directory(ctx, request["site_path"], receipt["metadata_snapshots"][0]["site_stat"])
        _runtime_check(ctx, request["site_path"])
        if _self_identity(ctx) != identity:
            raise CaptureError("actual self identity postvalidation drift", receipt)
        ctx.check()
    except Exception as error:
        _finish_partial(receipt)
        ctx.fail(error)
    finally:
        if root_fd is not None:
            try:
                ctx.close(root_fd)
            except Exception as error:
                ctx.fail(error)
    if ctx.t0 is None:
        # No invented work t0, marker or source work on prevalidation failure.
        # Bootstrap/prevalidation failure remains consumed by the caller.
        return 1
    if not ctx.failed:
        try:
            ctx.check()
            receipt.update(status="source_capture_candidate_ready", source_capture_complete=True)
        except Exception as error:
            ctx.fail(error)
    try:
        ctx.check(total=True)
        emit_json(receipt, 1, t0=ctx.t0)
    except Exception:
        # Unknown/partial stream remains original; no retry/repair output.
        return 1
    return 1 if ctx.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
