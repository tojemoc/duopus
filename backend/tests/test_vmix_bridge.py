import pytest

from services.vmix_bridge import VmixBridge, build_function_command, parse_tally_ok_line


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


def test_build_function_command_skips_input_kwarg():
    cmd = build_function_command("Cut", input=1, Input=2, Foo="x")
    assert cmd.count(b"Input=") == 1
    assert b"Input=1" in cmd
    assert b"Foo=" in cmd


def test_build_function_command_rejects_invalid_function_name():
    with pytest.raises(ValueError, match="function name"):
        build_function_command("Cut Bad")


def test_build_function_command_rejects_invalid_param_key():
    with pytest.raises(ValueError, match="parameter name"):
        build_function_command("Cut", input=1, **{"Bad Key": "x"})


def test_build_function_command_coerces_string_input():
    cmd = build_function_command("Cut", input=" 3 ")
    assert b"Input=3" in cmd


@pytest.mark.asyncio
async def test_bridge_publish_skipped_without_redis(monkeypatch):
    """Publish failures are swallowed so vMix loop can continue."""

    class DummyRedis:
        called = False

        async def publish(self, _ch, _data):
            self.called = True
            raise RuntimeError("redis down")

    bridge = VmixBridge(host="127.0.0.1", port=8099, redis_url="redis://unused")
    dummy = DummyRedis()
    bridge._redis = dummy  # noqa: SLF001
    parsed = parse_tally_ok_line("TALLY OK 1")
    assert parsed is not None
    bridge._tally = parsed  # noqa: SLF001
    await bridge._publish_tally()  # noqa: SLF001
    assert dummy.called is True
