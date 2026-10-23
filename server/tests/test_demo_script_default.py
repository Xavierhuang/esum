"""Demo mode uses the built-in demo script wherever it runs, not only under npm run dev."""
from opa.core.settings import Settings
from opa.worker.model import ScriptedAdapter, build_adapter


def _settings(**kw) -> Settings:
    return Settings(database_url="postgresql+asyncpg://unused@localhost/unused", model_provider="scripted", **kw)


async def test_demo_mode_without_a_script_path_uses_the_demo_script():
    adapter = build_adapter(_settings(mode="demo"))
    assert isinstance(adapter, ScriptedAdapter)
    r = await adapter.generate([{"role": "user", "content": "Connect my accounts"}], [], {}, system="")
    assert [c.name for c in r.tool_calls] == ["connections__request"]


async def test_an_explicit_script_path_still_wins(tmp_path):
    script = tmp_path / "s.yaml"
    script.write_text("default:\n  text: custom\n")
    r = await build_adapter(_settings(mode="demo", scripted_model_path=str(script))).generate([{"role": "user", "content": "Connect my accounts"}], [], {}, system="")
    assert r.text == "custom"
