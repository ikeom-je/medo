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


def test_keeps_safe_option_value_in_joined_form(tmp_path, monkeypatch):
    """結合形式でも選択結果をホスト間で比較できる必要がある。"""
    path = tmp_path / "trace.jsonl"
    monkeypatch.setenv("MEDO_TRACE", str(path))

    Tracer.from_env().record(["check", "add", "--result=undeterminable"], exit_code=0)

    entry = json.loads(path.read_text(encoding="utf-8").strip())
    assert entry["options"] == {"--result": "undeterminable"}


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


def test_redacts_free_text_in_joined_form(tmp_path, monkeypatch):
    """結合形式でも顧客の生の声をトレースに残してはならない。"""
    path = tmp_path / "trace.jsonl"
    monkeypatch.setenv("MEDO_TRACE", str(path))

    Tracer.from_env().record(
        ["facts", "save", "--statement=A社は年間3億円を紙処理に費やしている"],
        exit_code=0,
    )

    entry = json.loads(path.read_text(encoding="utf-8").strip())
    assert entry["options"] == {"--statement": "<redacted>"}


def test_redacts_file_paths(tmp_path, monkeypatch):
    """パスに顧客名が含まれうる。"""
    path = tmp_path / "trace.jsonl"
    monkeypatch.setenv("MEDO_TRACE", str(path))

    Tracer.from_env().record(["requirements", "save", "--file", "/home/x/A社/req.json"],
                             exit_code=0)

    entry = json.loads(path.read_text(encoding="utf-8").strip())
    assert entry["options"]["--file"] == "<redacted>"


def test_value_containing_equals_does_not_change_option_key(tmp_path, monkeypatch):
    """値に等号を含むファイルパスでもオプション名を保つ必要がある。"""
    path = tmp_path / "trace.jsonl"
    monkeypatch.setenv("MEDO_TRACE", str(path))

    Tracer.from_env().record(["requirements", "save", "--file=/path/a=b"], exit_code=0)

    entry = json.loads(path.read_text(encoding="utf-8").strip())
    assert entry["options"] == {"--file": "<redacted>"}


def test_free_text_starting_with_double_dash_is_not_recorded_as_key_or_value(
    tmp_path, monkeypatch
):
    """二重ハイフンで始まる顧客の自由文もキーにも値にも残してはならない。"""
    path = tmp_path / "trace.jsonl"
    monkeypatch.setenv("MEDO_TRACE", str(path))

    Tracer.from_env().record(
        ["facts", "save", "--statement", "-- 顧客要望による特急対応"],
        exit_code=0,
    )

    entry = json.loads(path.read_text(encoding="utf-8").strip())
    assert entry["options"] == {"--statement": "<redacted>"}


def test_option_terminator_is_not_recorded_as_an_option(tmp_path, monkeypatch):
    """オプション終端子はトレースのオプションに含めない。"""
    path = tmp_path / "trace.jsonl"
    monkeypatch.setenv("MEDO_TRACE", str(path))

    Tracer.from_env().record(["status", "--"], exit_code=0)

    entry = json.loads(path.read_text(encoding="utf-8").strip())
    assert entry["options"] == {}


def test_keeps_safe_joined_value_containing_equals(tmp_path, monkeypatch):
    """結合形式の安全な値に等号があってもオプション名と値を保つ。"""
    path = tmp_path / "trace.jsonl"
    monkeypatch.setenv("MEDO_TRACE", str(path))

    Tracer.from_env().record(["check", "add", "--result=a=b"], exit_code=0)

    entry = json.loads(path.read_text(encoding="utf-8").strip())
    assert entry["options"] == {"--result": "a=b"}


def test_keeps_empty_safe_value_in_joined_form(tmp_path, monkeypatch):
    """結合形式の空値は空文字として記録する。"""
    path = tmp_path / "trace.jsonl"
    monkeypatch.setenv("MEDO_TRACE", str(path))

    Tracer.from_env().record(["check", "add", "--result="], exit_code=0)

    entry = json.loads(path.read_text(encoding="utf-8").strip())
    assert entry["options"] == {"--result": ""}


def test_records_failures_so_skipped_recovery_is_visible(tmp_path, monkeypatch):
    path = tmp_path / "trace.jsonl"
    monkeypatch.setenv("MEDO_TRACE", str(path))

    Tracer.from_env().record(["status", "--project", "unknown"], exit_code=1)

    assert json.loads(path.read_text(encoding="utf-8").strip())["exit_code"] == 1


def test_never_raises_when_trace_path_is_unwritable(tmp_path, monkeypatch):
    """計測機構が本来の作業を止めてはならない。"""
    monkeypatch.setenv("MEDO_TRACE", str(tmp_path / "missing" / "trace.jsonl"))

    Tracer.from_env().record(["status"], exit_code=0)
