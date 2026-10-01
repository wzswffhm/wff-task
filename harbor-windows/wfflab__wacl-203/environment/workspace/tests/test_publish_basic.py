"""wpublish 的基础行为测试（仓库自带，不得修改）。"""

import pytest

from wpublish import deny, grant, list_aces, parse_aces, publish
from wpublish.rights import effective_rights

TEST_SID = "*S-1-5-32-546"

SAMPLE = """
ACL for C:\\data
                 BUILTIN\\Administrators:(F)
                 BUILTIN\\Users:(RX)
                 NT AUTHORITY\\SYSTEM:(OI)(CI)(F)
                 BUILTIN\\Guests:(DENY)(W)
"""


def test_parse_aces_reads_allow_entries():
    principals = {a.principal for a in parse_aces(SAMPLE)}
    assert "BUILTIN\\Administrators" in principals


def test_parse_aces_reads_deny_entries():
    denies = [a for a in parse_aces(SAMPLE) if a.deny]
    assert len(denies) == 1
    assert denies[0].principal == "BUILTIN\\Guests"


def test_parse_aces_skips_header_line():
    assert len(parse_aces(SAMPLE)) == 4


def test_list_aces_on_fresh_directory(tmp_path):
    assert list_aces(str(tmp_path))


def test_grant_then_list(tmp_path):
    grant(str(tmp_path), TEST_SID, "(RX)")
    assert list_aces(str(tmp_path))


def test_effective_rights_returns_sets(tmp_path):
    grant(str(tmp_path), TEST_SID, "(RX)")
    allow, deny = effective_rights(str(tmp_path), TEST_SID)
    assert isinstance(allow, set)
    assert isinstance(deny, set)


def test_publish_copies_content(tmp_path):
    src = tmp_path / "src"
    (src / "sub").mkdir(parents=True)
    (src / "sub" / "a.txt").write_bytes(b"payload")
    dst = tmp_path / "dst"
    publish(str(src), str(dst), TEST_SID)
    assert (dst / "sub" / "a.txt").read_bytes() == b"payload"
