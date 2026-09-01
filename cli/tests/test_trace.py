import json

from medo_cli.trace import Tracer


def test_disabled_when_env_is_unset(monkeypatch):
    monkeypatch.delenv("MEDO_TRACE", raising=False)

    assert Tracer.from_env() is None


def test_records_command_and_exit_code(tmp_path, monkeypatch):
    path = tmp_path / "trace.jsonl"
    monkeypatch.setenv("MEDO_TRACE", str(path))

    Tracer.from_env().record(["status", "--project", "p1"], exit_code=0)

    entry = json.loads(path.read_text(encoding="utf-8").strip())
    assert entry["command"] == ["status"]
    assert entry["exit_code"] == 0


def test_appends_so_a_whole_round_forms_one_trace(tmp_path, monkeypatch):
    path = tmp_path / "trace.jsonl"
    monkeypatch.setenv("MEDO_TRACE", str(path))
    tracer = Tracer.from_env()

    tracer.record(["status", "--project", "p1"], exit_code=0)
    tracer.record(["check", "add", "--project", "p1"], exit_code=0)

    assert [json.loads(x)["command"] for x in path.read_text(encoding="utf-8").splitlines()] == [
        ["status"], ["check", "add"]
    ]


def test_keeps_values_of_decision_relevant_options(tmp_path, monkeypatch):
    """どの選択肢を選んだかはホスト間比較の対象なので値を残す。"""
    path = tmp_path / "trace.jsonl"
    monkeypatch.setenv("MEDO_TRACE", str(path))

    Tracer.from_env().record(
        ["check", "add", "--check", "reality_gap", "--result", "undeterminable",
         "--disposition", "promoted"],
        exit_code=0,
    )

    entry = json.loads(path.read_text(encoding="utf-8").strip())
    assert entry["options"]["--result"] == "undeterminable"
    assert entry["options"]["--disposition"] == "promoted"


def test_redacts_free_text_values(tmp_path, monkeypatch):
    """顧客の生の声がトレースに残ると、リポジトリ外に出せなくなる。"""
    path = tmp_path / "trace.jsonl"
    monkeypatch.setenv("MEDO_TRACE", str(path))

    Tracer.from_env().record(
        ["facts", "save", "--statement", "A社は年間3億円を紙処理に費やしている"],
        exit_code=0,
    )

    entry = json.loads(path.read_text(encoding="utf-8").strip())
    assert entry["options"]["--statement"] == "<redacted>"


def test_redacts_file_paths(tmp_path, monkeypatch):
    """パスに顧客名が含まれうる。"""
    path = tmp_path / "trace.jsonl"
    monkeypatch.setenv("MEDO_TRACE", str(path))

    Tracer.from_env().record(["requirements", "save", "--file", "/home/x/A社/req.json"],
                             exit_code=0)

    entry = json.loads(path.read_text(encoding="utf-8").strip())
    assert entry["options"]["--file"] == "<redacted>"


def test_records_failures_so_skipped_recovery_is_visible(tmp_path, monkeypatch):
    path = tmp_path / "trace.jsonl"
    monkeypatch.setenv("MEDO_TRACE", str(path))

    Tracer.from_env().record(["status", "--project", "unknown"], exit_code=1)

    assert json.loads(path.read_text(encoding="utf-8").strip())["exit_code"] == 1


def test_never_raises_when_trace_path_is_unwritable(tmp_path, monkeypatch):
    """計測機構が本来の作業を止めてはならない。"""
    monkeypatch.setenv("MEDO_TRACE", str(tmp_path / "missing" / "trace.jsonl"))

    Tracer.from_env().record(["status"], exit_code=0)
