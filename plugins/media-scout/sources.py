"""Deterministic, network-free parsing of supported media source URLs."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from urllib.parse import parse_qsl, urlsplit, urlunsplit

MAX_URL = 2048
MAX_TEXT = 16000
_TOKEN = re.compile(r"[A-Za-z0-9_-]{1,128}\Z", re.ASCII)
_SHORTCODE = re.compile(r"[A-Za-z0-9_-]{5,20}\Z", re.ASCII)
_DIGITS = re.compile(r"[0-9]{1,128}\Z", re.ASCII)
_YT = re.compile(r"[A-Za-z0-9_-]{11}\Z", re.ASCII)
_HANDLE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,62})\Z", re.ASCII)
_KNOWN_HOSTS = {
    "instagram.com", "www.instagram.com", "youtube.com", "www.youtube.com", "m.youtube.com",
    "music.youtube.com", "youtube-nocookie.com", "www.youtube-nocookie.com", "youtu.be",
    "tiktok.com", "www.tiktok.com", "vm.tiktok.com", "vt.tiktok.com", "threads.net",
    "www.threads.net", "threads.com", "www.threads.com", "snapchat.com", "www.snapchat.com",
    "x.com", "www.x.com", "mobile.x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com",
    "reddit.com", "www.reddit.com", "old.reddit.com", "new.reddit.com", "m.reddit.com", "redd.it",
    "v.redd.it", "facebook.com", "www.facebook.com", "m.facebook.com", "mbasic.facebook.com",
    "vimeo.com", "www.vimeo.com", "player.vimeo.com", "bsky.app",
}


@dataclass(frozen=True)
class Source:
    platform: str
    post_id: str
    identity_key: str
    original_url: str
    canonical_url: str
    title: str
    identity_quality: str


def _title(platform: str, post_id: str, share: bool = False) -> str:
    base = platform + ("_share_" if share else "_")
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", post_id)
    room = 100 - len(base)
    if len(safe) <= room:
        return base + safe
    suffix = "_" + hashlib.sha256(post_id.encode("utf-8")).hexdigest()[:12]
    return base + safe[:room-len(suffix)] + suffix


def _make(platform: str, post_id: str, original: str, canonical: str, *, share: bool = False) -> Source:
    key = (platform + ":share:" + post_id) if share else (post_id if platform == "instagram" else platform + ":" + post_id)
    return Source(platform, post_id, key, original, canonical, _title(platform, post_id, share),
                  "share-link" if share else "canonical")


def _safe_parts(value: str):
    if not isinstance(value, str) or not value or len(value) > MAX_URL or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value):
        return None
    if "\\" in value or not value.lower().startswith("https://"):
        return None
    try:
        p = urlsplit(value)
        if p.scheme != "https" or p.username is not None or p.password is not None or p.hostname is None:
            return None
        # Reject all explicit authority ports, including the otherwise empty trailing colon.
        authority = p.netloc.rsplit("@", 1)[-1]
        if ":" in authority or "%" in p.path or "//" in p.path or any(x in (".", "..") for x in p.path.split("/")):
            return None
        host = p.hostname.lower()
        if host not in _KNOWN_HOSTS:
            return None
        return p, host
    except (ValueError, UnicodeError):
        return None


def parse_source_url(value: str) -> Source | None:
    pair = _safe_parts(value)
    if not pair:
        return None
    p, host = pair
    path = p.path
    qs = parse_qsl(p.query, keep_blank_values=True, strict_parsing=False)
    qmap: dict[str, list[str]] = {}
    for k, v in qs:
        qmap.setdefault(k, []).append(v)

    def query_one(name: str):
        vals = qmap.get(name, [])
        return vals[0] if len(vals) == 1 else None

    # Instagram keeps the historic shortcode as its raw database identity.
    if host in {"instagram.com", "www.instagram.com"}:
        m = re.fullmatch(r"/(?:reel|p|tv)/([A-Za-z0-9_-]{5,20})/?", path, re.ASCII)
        if m:
            return _make("instagram", m.group(1), value, "https://www.instagram.com/p/" + m.group(1) + "/")
        return None

    if host in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtube-nocookie.com", "www.youtube-nocookie.com", "youtu.be"}:
        vid = None
        if host == "youtu.be":
            m = re.fullmatch(r"/([A-Za-z0-9_-]{11})/?", path, re.ASCII)
            vid = m.group(1) if m else None
        elif path == "/watch":
            vid = query_one("v")
            if any(k == "v" for k, _ in qs) and vid is None:
                return None
            if vid and not _YT.fullmatch(vid): return None
        else:
            m = re.fullmatch(r"/(?:shorts|embed)/([A-Za-z0-9_-]{11})/?", path, re.ASCII)
            vid = m.group(1) if m else None
        if vid and _YT.fullmatch(vid):
            return _make("youtube", vid, value, "https://www.youtube.com/watch?v=" + vid)
        return None

    if host in {"tiktok.com", "www.tiktok.com"}:
        m = re.fullmatch(r"/@([A-Za-z0-9._-]{1,64})/(video|photo)/([0-9]{1,128})/?", path, re.ASCII)
        if m and _HANDLE.fullmatch(m.group(1)):
            pid = m.group(3)
            return _make("tiktok", pid, value, f"https://www.tiktok.com/@{m.group(1)}/{m.group(2)}/{pid}")
        m = re.fullmatch(r"/t/([A-Za-z0-9_-]{1,128})/?", path, re.ASCII)
        if m: return _make("tiktok", m.group(1), value, f"https://www.tiktok.com/t/{m.group(1)}", share=True)
        return None
    if host in {"vm.tiktok.com", "vt.tiktok.com"}:
        m = re.fullmatch(r"/([A-Za-z0-9_-]{1,128})/?", path, re.ASCII)
        return _make("tiktok", m.group(1), value, "https://" + host + "/" + m.group(1) + "/", share=True) if m else None

    if host in {"threads.net", "www.threads.net", "threads.com", "www.threads.com"}:
        m = re.fullmatch(r"/@([A-Za-z0-9._-]{1,64})/post/([A-Za-z0-9_-]{1,128})/?", path, re.ASCII)
        if m and _HANDLE.fullmatch(m.group(1)):
            pid = m.group(2)
            return _make("threads", pid, value, "https://www.threads.com/@" + m.group(1) + "/post/" + m.group(2))
        return None
    if host in {"snapchat.com", "www.snapchat.com"}:
        m = re.fullmatch(r"/spotlight/([A-Za-z0-9_-]{1,128})/?", path, re.ASCII)
        if m: return _make("snapchat", m.group(1), value, "https://www.snapchat.com/spotlight/" + m.group(1))
        m = re.fullmatch(r"/t/([A-Za-z0-9_-]{1,128})/?", path, re.ASCII)
        if m: return _make("snapchat", m.group(1), value, "https://www.snapchat.com/t/" + m.group(1), share=True)
        return None

    if host in {"x.com", "www.x.com", "mobile.x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com"}:
        m = re.fullmatch(r"/(?:([A-Za-z0-9_]{1,15})|i)/status/([0-9]{1,128})/?", path, re.ASCII)
        if m: return _make("x", m.group(2), value, "https://x.com/" + (m.group(1) or "i") + "/status/" + m.group(2))
        return None

    if host in {"reddit.com", "www.reddit.com", "old.reddit.com", "new.reddit.com", "m.reddit.com"}:
        direct = re.fullmatch(r"/comments/([A-Za-z0-9]{1,32})/?", path, re.ASCII)
        if direct:
            return _make("reddit", direct.group(1), value, "https://www.reddit.com/comments/" + direct.group(1) + "/")
        m = re.fullmatch(r"/r/([A-Za-z0-9_]{1,64})/comments/([A-Za-z0-9]{1,32})(?:/[A-Za-z0-9_-]{1,160})?/?", path, re.ASCII)
        if m: return _make("reddit", m.group(2), value, "https://www.reddit.com/r/" + m.group(1) + "/comments/" + m.group(2) + "/")
        return None
    if host == "redd.it":
        m = re.fullmatch(r"/([A-Za-z0-9]{1,32})/?", path, re.ASCII)
        return _make("reddit", m.group(1), value, "https://www.reddit.com/comments/" + m.group(1) + "/") if m else None
    if host == "v.redd.it":
        m = re.fullmatch(r"/([A-Za-z0-9_-]{1,128})/?", path, re.ASCII)
        return _make("reddit", m.group(1), value, "https://v.redd.it/" + m.group(1), share=True) if m else None

    if host in {"facebook.com", "www.facebook.com", "m.facebook.com", "mbasic.facebook.com"}:
        m = re.fullmatch(r"/reel/([0-9]{1,128})/?", path, re.ASCII)
        pid = m.group(1) if m else None
        if path in {"/watch", "/watch/"} and any(k == "v" for k, _ in qs):
            pid = query_one("v")
            if pid and not _DIGITS.fullmatch(pid): return None
        if not pid:
            m = re.fullmatch(r"/([A-Za-z0-9._-]{1,64})/videos/([0-9]{1,128})/?", path, re.ASCII)
            pid = m.group(2) if m else None
        if pid: return _make("facebook", pid, value, "https://www.facebook.com/watch/?v=" + pid)
        return None
    if host in {"vimeo.com", "www.vimeo.com", "player.vimeo.com"}:
        pathpat = r"/video/([0-9]{1,128})/?" if host == "player.vimeo.com" else r"/([0-9]{1,128})/?"
        m = re.fullmatch(pathpat, path, re.ASCII)
        if m: return _make("vimeo", m.group(1), value, "https://vimeo.com/" + m.group(1))
        return None
    if host == "bsky.app":
        m = re.fullmatch(r"/profile/(did:plc:[A-Za-z0-9]{20,64}|[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251})\.[A-Za-z]{2,63})/post/([A-Za-z0-9]{1,128})/?", path, re.ASCII)
        if m:
            pid = m.group(1) + ":" + m.group(2)
            return _make("bluesky", pid, value, "https://bsky.app/profile/" + m.group(1) + "/post/" + m.group(2))
        return None
    return None


_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


def extract_one_source(text: str) -> Source | None:
    if not isinstance(text, str) or len(text) > MAX_TEXT:
        return None
    found: list[Source] = []
    for match in _URL_RE.finditer(text):
        raw = match.group(0).rstrip(".,;:!?)]}")
        try:
            host = urlsplit(raw).hostname
        except ValueError:
            host = None
        parsed = parse_source_url(raw)
        if parsed:
            found.append(parsed)
        elif host:
            h = host.lower()
            if h in _KNOWN_HOSTS or any(h.startswith(k + ".") for k in _KNOWN_HOSTS):
                return None
    if not found or len({s.identity_key for s in found}) != 1:
        return None
    return found[0]


def source_for_key(key: str) -> tuple[str, str] | None:
    if not isinstance(key, str): return None
    if _SHORTCODE.fullmatch(key): return ("instagram", key)
    platform, sep, rest = key.partition(":")
    if not sep or platform not in {"youtube", "tiktok", "threads", "snapchat", "x", "reddit", "facebook", "vimeo", "bluesky"}:
        return None
    if rest.startswith("share:"):
        token = rest[6:]
        return (platform, "share:" + token) if _TOKEN.fullmatch(token) else None
    return (platform, rest) if rest and len(rest) <= 300 else None
