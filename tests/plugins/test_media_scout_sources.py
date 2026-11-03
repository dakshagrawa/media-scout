import importlib.util
from pathlib import Path
import sys

MODULE = Path(__file__).parents[2] / "plugins" / "media-scout" / "sources.py"
spec = importlib.util.spec_from_file_location("media_scout_sources", MODULE)
sources = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = sources
spec.loader.exec_module(sources)


def parse(url):
    return sources.parse_source_url(url)


def test_instagram_compatibility_and_original_context():
    s = parse("https://www.instagram.com/p/AbC123/?img_index=2&utm_source=x#frame")
    assert (s.platform, s.post_id, s.identity_key) == ("instagram", "AbC123", "AbC123")
    assert s.original_url.endswith("?img_index=2&utm_source=x#frame")
    assert s.canonical_url == "https://www.instagram.com/p/AbC123/"
    assert s.identity_quality == "canonical"


def test_video_aliases_and_platform_namespaces():
    urls = ["https://youtube.com/watch?v=AbCdEf12345", "https://youtu.be/AbCdEf12345",
            "https://m.youtube.com/shorts/AbCdEf12345", "https://youtube-nocookie.com/embed/AbCdEf12345"]
    parsed = [parse(u) for u in urls]
    assert all(x.identity_key == "youtube:AbCdEf12345" for x in parsed)
    assert parse("https://x.com/A/status/123456789012345678") .identity_key == "x:123456789012345678"
    assert parse("https://redd.it/123abc").identity_key == "reddit:123abc"
    assert parse("https://vimeo.com/12345").identity_key != "facebook:12345"


def test_supported_platform_shapes_and_case():
    cases = {
        "https://www.tiktok.com/@Some.User/video/1234567890123456789": ("tiktok", "1234567890123456789"),
        "https://www.tiktok.com/@Some.User/photo/1234567890123456789": ("tiktok", "1234567890123456789"),
        "https://threads.com/@SomeUser/post/AbC123": ("threads", "AbC123"),
        "https://www.snapchat.com/spotlight/AbC123": ("snapchat", "AbC123"),
        "https://www.facebook.com/User/videos/12345678901234567890": ("facebook", "12345678901234567890"),
        "https://bsky.app/profile/Some.Handle/post/AbC123": ("bluesky", "Some.Handle:AbC123"),
    }
    for url, expected in cases.items():
        s = parse(url)
        assert (s.platform, s.post_id) == expected


def test_provisional_share_links_are_distinct_and_bounded():
    a = parse("https://vm.tiktok.com/ZM123abc/")
    b = parse("https://www.tiktok.com/t/ZM123abc")
    assert a.identity_quality == b.identity_quality == "share-link"
    assert a.identity_key == b.identity_key == "tiktok:share:ZM123abc"
    assert parse("https://www.snapchat.com/t/Share123").identity_key == "snapchat:share:Share123"
    assert len(a.title) <= 100 and a.title == "tiktok_share_ZM123abc"


def test_reddit_post_identity_and_provisional_media():
    a = parse("https://www.reddit.com/r/Python/comments/AbC123/a_post/?context=3")
    assert a.identity_key == "reddit:AbC123"
    assert a.original_url.endswith("?context=3")
    assert parse("https://v.redd.it/AbC123").identity_key == "reddit:share:AbC123"


def test_extract_single_identity_aliases_and_reject_ambiguity_or_malformed_social():
    assert sources.extract_one_source("See https://youtu.be/AbCdEf12345 or https://youtube.com/watch?v=AbCdEf12345")
    assert sources.extract_one_source("https://youtu.be/AbCdEf12345 https://instagram.com/p/AbC123") is None
    assert sources.extract_one_source("https://instagram.com/p/AbC123 https://instagram.com.evil/p/Bad123") is None
    assert sources.extract_one_source("https://instagram.com/p/AbC123 https://x.com/a/status/nope") is None
    assert sources.extract_one_source("reference https://example.com/article") is None


def test_rejects_noncontent_and_unsafe_url_forms():
    bad = ["http://instagram.com/p/AbC123", "https://instagram.com.evil/p/AbC123",
           "https://u@instagram.com/p/AbC123", "https://instagram.com:443/p/AbC123",
           "https://instagram.com:/p/AbC123", "https://instagram.com/p/%2e%2e",
           "https://instagram.com/p/a%2fbcd", "https://youtube.com/watch?v=AbCdEf12345&v=QwErTy12345",
           "https://youtube.com/playlist?list=PL123", "https://www.snapchat.com/add/user",
           "https://www.snapchat.com/privateSnaps/user", "https://x.com/user/status/1.0",
           "https://reddit.com/r/test/comments/AbC123/title/Def456",
           "https://instagram.com//p/AbC123", "https://instagram.com/p/AbC123\\@evil"]
    assert all(parse(url) is None for url in bad)
    assert parse("https://x.com/a/status/900719925474099312345").post_id == "900719925474099312345"


def test_source_for_key_and_title_safety():
    assert sources.source_for_key("AbC123") == ("instagram", "AbC123")
    assert sources.source_for_key("youtube:AbCdEf12345") == ("youtube", "AbCdEf12345")
    assert sources.source_for_key("tiktok:share:AbC") == ("tiktok", "share:AbC")
    s = parse("https://bsky.app/profile/did:plc:abcdefghijklmnopqrst/post/AbC123")
    assert s and s.title.startswith("bluesky_") and len(s.title) <= 100
    assert all(c.isalnum() or c in "_-" for c in s.title)
    assert parse("https://bsky.app/profile/did:plc:abcdefghijklmnopqrst/post/AbC123").identity_key != parse(
        "https://bsky.app/profile/did:plc:zyxwvutsrqponmlkjihgf/post/AbC123").identity_key


def test_canonical_outputs_are_reparseable_and_thread_id_is_global():
    urls = ["https://facebook.com/watch/?v=12345", "https://www.reddit.com/comments/abc123/", "https://threads.com/@OldName/post/AbC123"]
    for url in urls:
        source = parse(url)
        assert source is not None, url
        assert parse(source.canonical_url).identity_key == source.identity_key
    assert parse("https://threads.com/@OldName/post/AbC123").identity_key == parse("https://threads.net/@NewName/post/AbC123").identity_key


def test_legacy_scheme_case_and_http_ambiguity_are_not_silently_lost():
    source = parse("HTTPS://WWW.INSTAGRAM.COM/p/AbC123/")
    assert source and source.original_url.startswith("HTTPS://")
    assert sources.extract_one_source("https://youtu.be/AbCdEf12345 http://instagram.com/p/Other1") is None
