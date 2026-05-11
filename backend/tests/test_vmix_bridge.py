import pytest

from services.vmix_bridge import build_function_command, parse_tally_ok_line


def test_parse_tally_ok_basic():
    t = parse_tally_ok_line("TALLY OK 012")
    assert t is not None
    assert t.program_input == 2
    assert t.preview_input == 3
    assert t.by_input[1] == 0
    assert t.by_input[2] == 1
    assert t.by_input[3] == 2


def test_parse_tally_ok_ignores_non_tally():
    assert parse_tally_ok_line("SUBSCRIBE OK TALLY") is None
    assert parse_tally_ok_line("FUNCTION OK Completed") is None


def test_build_function_command_cut():
    cmd = build_function_command("Cut", input=3)
    assert cmd == b"FUNCTION Cut Input=3\r\n"


def test_build_function_command_extra_params():
    cmd = build_function_command("SetText", input=1, SelectedName="Headline", Value="Hi")
    assert cmd.startswith(b"FUNCTION SetText ")
    assert b"Input=1" in cmd
    assert b"SelectedName=" in cmd


@pytest.mark.asyncio
async def test_bridge_publish_skipped_without_redis(monkeypatch):
    """Smoke: parse path only; full bridge needs TCP."""
    assert parse_tally_ok_line("TALLY OK 1") is not None
