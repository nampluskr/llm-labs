"""대화 저장 형식(D-7): 메시지 순서·role 보존, 한글 인코딩, 손상된 파일 거절, 저장 도중 실패해도 기존 파일 보존."""

import json
import os

import pytest

from local_chat import conversation
from local_chat.conversation import ConversationError, load_file, parse, save_file

SAMPLE = [
    {"role": "user", "content": "안녕하세요 😊\n두 번째 줄\t탭"},
    {"role": "assistant", "content": '큰따옴표 " 와 역슬래시 \\ 와 \\u00e9 그대로, 유니코드 줄바꿈   도, 널 아닌 제어문자 \x01'},
    {"role": "user", "content": "한 줄"},
    {"role": "assistant", "content": "답 " * 5000},  # 긴 답
]


def test_저장했다_다시_열면_같은_메시지_수와_순서와_role로_복원된다(tmp_path):
    path = tmp_path / "chat.json"
    save_file(path, SAMPLE, "qwen3:8b")
    assert load_file(path) == SAMPLE
    assert [m["role"] for m in load_file(path)] == ["user", "assistant", "user", "assistant"]


def test_파일은_UTF8이고_한글을_이스케이프하지_않는다(tmp_path):
    path = tmp_path / "chat.json"
    save_file(path, SAMPLE, "qwen3:8b")
    raw = path.read_bytes()
    assert "안녕하세요 😊".encode("utf-8") in raw  # 사람이 편집기에서 읽을 수 있다
    assert b"\\ud" not in raw.lower()  # 서로게이트 쌍 이스케이프가 아니다
    assert b"\r\n" not in raw  # 줄바꿈은 LF
    doc = json.loads(raw.decode("utf-8"))
    assert doc["format"] == "local-chat" and doc["version"] == 1 and doc["model"] == "qwen3:8b" and doc["saved_at"]


def test_한글_폴더와_파일_이름에도_저장하고_연다(tmp_path):
    folder = tmp_path / "대화 저장 폴더"
    folder.mkdir()
    path = folder / "한글 파일 이름.json"
    save_file(path, SAMPLE)
    assert load_file(path) == SAMPLE
    assert [p.name for p in folder.iterdir()] == ["한글 파일 이름.json"]  # 임시 파일이 남지 않았다


def test_빈_대화도_저장하고_열_수_있다(tmp_path):
    path = tmp_path / "empty.json"
    save_file(path, [])
    assert load_file(path) == []


def test_messages_배열만_있는_파일과_버전이_없는_객체도_읽는다():
    assert parse(json.dumps(SAMPLE[:2])) == SAMPLE[:2]
    assert parse(json.dumps({"messages": SAMPLE[:2]})) == SAMPLE[:2]


def test_알려진_필드만_복원한다():
    messages = [{"role": "user", "content": "q", "extra": 1, "thinking": "x"}, {"role": "assistant", "content": "a", "model": "m"}]
    assert parse(json.dumps(messages)) == [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}]


def u(content="q"):
    return {"role": "user", "content": content}


def a(content="a"):
    return {"role": "assistant", "content": content}


@pytest.mark.parametrize(
    "text",
    [
        "",
        "not json",
        '{"messages": [',  # 잘리거나 깨진 JSON
        '{"messages": [{"role": "user", "content": "q"}, {"role": "assis',
        "null",
        "5",
        '"문자열"',
        "{}",  # messages 없음
        '{"messages": "oops"}',
        '{"messages": {"role": "user"}}',
        '{"version": 2, "messages": []}',
        '{"version": true, "messages": []}',
        '{"version": "1", "messages": []}',
        json.dumps([5]),
        json.dumps([None]),
        json.dumps([[u()]]),
        json.dumps([{"content": "q"}]),  # role 없음
        json.dumps([{"role": "system", "content": "s"}, a()]),  # 시스템 메시지는 저장하지 않는다
        json.dumps([{"role": "tool", "content": "t"}, a()]),
        json.dumps([{"role": "USER", "content": "q"}, a()]),
        json.dumps([a(), u()]),  # assistant로 시작
        json.dumps([u(), u()]),  # 질문이 연달아
        json.dumps([u(), a(), a(), u()]),  # 답이 연달아
        json.dumps([u()]),  # 마지막 질문에 답이 없다
        json.dumps([u(), a(), u()]),
        json.dumps([u(1), a()]),  # content가 문자열이 아니다
        json.dumps([u(None), a()]),
        json.dumps([u(["q"]), a()]),
        json.dumps([u(""), a()]),  # 빈 메시지
        json.dumps([u("   \n"), a()]),
        json.dumps([u(), a("")]),
        pytest.param("[" * 5000 + "]" * 5000, id="깊게_중첩된_배열"),  # 너무 깊게 중첩된 JSON(RecursionError). id가 길면 환경 변수 한계를 넘는다
        pytest.param('{"messages": ' * 5000 + "[]" + "}" * 5000, id="깊게_중첩된_객체"),
    ],
)
def test_손상되거나_올바르지_않은_내용은_예외_없이_ConversationError(text):
    with pytest.raises(ConversationError) as e:
        parse(text)
    assert str(e.value)  # 사람이 읽을 문구가 있다


def test_BOM이_붙은_UTF8_파일도_읽는다(tmp_path):
    path = tmp_path / "bom.json"
    path.write_bytes(b"\xef\xbb\xbf" + json.dumps({"messages": SAMPLE}, ensure_ascii=False).encode("utf-8"))
    assert load_file(path) == SAMPLE


def test_UTF8이_아닌_파일은_거절한다(tmp_path):
    path = tmp_path / "cp949.json"
    path.write_bytes(json.dumps({"messages": [u("안녕"), a("반갑습니다")]}, ensure_ascii=False).encode("cp949"))  # 한글 메모장 기본 저장
    with pytest.raises(ConversationError, match="UTF-8"):
        load_file(path)
    path.write_bytes(b"\xff\xfe\x00\x00 not utf8")
    with pytest.raises(ConversationError, match="UTF-8"):
        load_file(path)


def test_없는_파일_폴더_권한이_없는_경우는_ConversationError(tmp_path):
    with pytest.raises(ConversationError, match="읽지 못했다"):
        load_file(tmp_path / "없음.json")
    with pytest.raises(ConversationError, match="읽지 못했다"):
        load_file(tmp_path)  # 폴더


def test_너무_큰_파일은_읽지_않는다(tmp_path, monkeypatch):
    monkeypatch.setattr(conversation, "MAX_BYTES", 1000)
    path = tmp_path / "big.json"
    path.write_text(json.dumps([u("가" * 2000), a("답")], ensure_ascii=False), encoding="utf-8")  # 저장은 한도를 넘으면 거절하므로 직접 쓴다
    with pytest.raises(ConversationError, match="너무 크다"):
        load_file(path)


def test_없는_폴더에는_저장하지_못하고_아무것도_만들지_않는다(tmp_path):
    with pytest.raises(ConversationError, match="저장하지 못했다"):
        save_file(tmp_path / "없는폴더" / "chat.json", SAMPLE)
    assert list(tmp_path.iterdir()) == []


def test_저장_도중_교체에_실패해도_기존_파일은_그대로고_임시_파일은_남지_않는다(tmp_path, monkeypatch):
    path = tmp_path / "chat.json"
    save_file(path, [u("옛 질문"), a("옛 답")])
    before = path.read_bytes()

    def boom(src, dst):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(conversation.os, "replace", boom)
    with pytest.raises(ConversationError, match="저장하지 못했다"):
        save_file(path, SAMPLE)
    assert path.read_bytes() == before  # 반쯤 쓴 파일이 기존 파일을 덮지 않았다
    assert [p.name for p in tmp_path.iterdir()] == ["chat.json"]
    assert load_file(path) == [u("옛 질문"), a("옛 답")]


def test_쓰기_도중_실패해도_기존_파일은_그대로다(tmp_path, monkeypatch):
    path = tmp_path / "chat.json"
    save_file(path, [u("옛 질문"), a("옛 답")])
    before = path.read_bytes()
    monkeypatch.setattr(conversation.os, "fsync", lambda fd: (_ for _ in ()).throw(OSError(5, "I/O error")))
    with pytest.raises(ConversationError):
        save_file(path, SAMPLE)
    assert path.read_bytes() == before and [p.name for p in tmp_path.iterdir()] == ["chat.json"]


def test_UTF8로_쓸_수_없는_문자는_거절하고_기존_파일은_그대로다(tmp_path):
    path = tmp_path / "chat.json"
    save_file(path, [u("옛 질문"), a("옛 답")])
    before = path.read_bytes()
    with pytest.raises(ConversationError, match="UTF-8"):
        save_file(path, [u("짝 없는 서로게이트 \ud83d"), a("답")])
    assert path.read_bytes() == before and [p.name for p in tmp_path.iterdir()] == ["chat.json"]


def test_같은_경로에_다시_저장하면_교체된다(tmp_path):
    path = tmp_path / "chat.json"
    save_file(path, [u("1"), a("1")])
    save_file(path, SAMPLE)
    assert load_file(path) == SAMPLE and os.listdir(tmp_path) == ["chat.json"]


def test_JSON_이스케이프로_든_짝_없는_서로게이트는_거절한다():
    """받아들이면 이후 모든 요청이 UTF-8 인코딩 오류로 실패하고, 그 대화는 저장도 못 한다."""
    for escaped in ('"\\ud800"', '"앞\\udc00뒤"', '"\\ud83d"'):
        text = '[{"role": "user", "content": %s}, {"role": "assistant", "content": "a"}]' % escaped
        with pytest.raises(ConversationError, match="UTF-8"):
            parse(text)
        text = '[{"role": "user", "content": "q"}, {"role": "assistant", "content": %s}]' % escaped
        with pytest.raises(ConversationError, match="UTF-8"):
            parse(text)
    # 짝이 맞는 서로게이트 쌍(이모지)은 정상이다
    assert parse('[{"role": "user", "content": "\\ud83d\\ude0a"}, {"role": "assistant", "content": "a"}]')[0]["content"] == "😊"


def test_format이_다르면_거절하고_없거나_같으면_받는다():
    assert parse(json.dumps({"format": "local-chat", "messages": SAMPLE[:2]})) == SAMPLE[:2]
    assert parse(json.dumps({"messages": SAMPLE[:2]})) == SAMPLE[:2]
    for fmt in ("other-app", "", None, 1, ["local-chat"]):
        with pytest.raises(ConversationError, match="format"):
            parse(json.dumps({"format": fmt, "messages": SAMPLE[:2]}))


@pytest.mark.parametrize(
    "text",
    [
        '{"messages": [], "messages": []}',
        '{"messages": [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}], "messages": []}',
        '{"messages": [{"role": "system", "role": "user", "content": "q"}, {"role": "assistant", "content": "a"}]}',
        '{"messages": [{"role": "user", "content": null, "content": "q"}, {"role": "assistant", "content": "a"}]}',
        '{"version": 2, "version": 1, "messages": []}',
        '[{"role": "user", "content": "q", "content": "r"}, {"role": "assistant", "content": "a"}]',
    ],
)
def test_중복된_키는_마지막_값으로_덮어쓰지_않고_거절한다(text):
    with pytest.raises(ConversationError, match="같은 키"):
        parse(text)


def test_저장_결과가_읽기_한도를_넘으면_저장하지_않고_넘지_않으면_항상_다시_열_수_있다(tmp_path, monkeypatch):
    path = tmp_path / "chat.json"
    save_file(path, SAMPLE, "qwen3:8b")
    size = path.stat().st_size
    monkeypatch.setattr(conversation, "MAX_BYTES", size)
    path.unlink()
    save_file(path, SAMPLE, "qwen3:8b")  # 한도와 같으면 저장되고
    assert load_file(path) == SAMPLE  # 다시 열린다
    before = path.read_bytes()
    monkeypatch.setattr(conversation, "MAX_BYTES", size - 1)
    with pytest.raises(ConversationError, match="너무 커서"):
        save_file(path, SAMPLE, "qwen3:8b")  # 한도를 넘으면 거절하고
    assert path.read_bytes() == before and [p.name for p in tmp_path.iterdir()] == ["chat.json"]  # 기존 파일과 폴더가 그대로다


def test_열기_한도_바로_아래의_파일을_복원해_다시_저장해도_열_수_있거나_저장이_거절된다(tmp_path):
    """한도 근처의 파일은 들여쓰기·메타데이터가 붙는 저장 결과가 한도를 넘을 수 있다. 그 경우 조용히 읽을 수 없는 파일을 만들지 않는다."""
    big = "q" * (conversation.MAX_BYTES - 120)  # 압축 JSON 파일이 한도 바로 아래가 되게 한다
    raw = json.dumps([{"role": "user", "content": big}, {"role": "assistant", "content": "a"}], separators=(",", ":"))
    src = tmp_path / "near_limit.json"
    src.write_text(raw, encoding="utf-8")
    assert src.stat().st_size <= conversation.MAX_BYTES
    messages = load_file(src)
    dst = tmp_path / "saved.json"
    try:
        save_file(dst, messages)
    except ConversationError as e:
        assert "너무 커서" in str(e) and not dst.exists()  # 저장이 거절됐다
    else:
        assert load_file(dst) == messages  # 저장됐다면 다시 열린다


def test_키가_아주_많은_파일의_중복_키_검사가_제곱_시간이_아니다():
    """중복을 목록 검색으로 찾으면 키 10만 개에서 수십억 번 비교한다. 파일 크기 한도로는 처리 시간이 제한되지 않는다."""
    import time

    keys = ",".join(f'"k{i}":0' for i in range(100_000))
    text = "{" + keys + ',"k99999":1,"messages":[]}'
    assert len(text) < conversation.MAX_BYTES
    t0 = time.perf_counter()
    with pytest.raises(ConversationError, match="같은 키"):
        parse(text)
    assert time.perf_counter() - t0 < 3


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_JSON에_없는_숫자_상수는_거절하고_현재_대화를_지우지_않는다(constant):
    for text in ('{"messages": [], "model": %s}' % constant, '{"messages": [], "x": [%s]}' % constant, '[%s]' % constant):
        with pytest.raises(ConversationError):
            parse(text)


def test_메시지_수_상한을_읽기와_저장_모두에_건다(tmp_path, monkeypatch):
    monkeypatch.setattr(conversation, "MAX_MESSAGES", 4)
    pairs = [u("1"), a("1"), u("2"), a("2")]
    assert parse(json.dumps(pairs)) == pairs  # 상한과 같으면 읽는다
    with pytest.raises(ConversationError, match="너무 많다"):
        parse(json.dumps(pairs + [u("3"), a("3")]))
    path = tmp_path / "chat.json"
    save_file(path, pairs)  # 상한과 같으면 저장되고
    assert load_file(path) == pairs  # 다시 열린다
    with pytest.raises(ConversationError, match="너무 많아"):
        save_file(path, pairs + [u("3"), a("3")])  # 넘으면 저장하지 않는다
    assert load_file(path) == pairs  # 기존 파일은 그대로다


def test_쓰기_중_실패와_임시_파일_정리_실패에도_ConversationError이고_기존_파일은_그대로다(tmp_path, monkeypatch):
    path = tmp_path / "chat.json"
    save_file(path, [u("옛 질문"), a("옛 답")])
    before = path.read_bytes()
    real_fdopen = os.fdopen

    class FailingFile:
        def __init__(self, f):
            self._f = f

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self._f.close()

        def write(self, data):
            raise OSError(28, "No space left on device")

    monkeypatch.setattr(conversation.os, "fdopen", lambda fd, *a, **k: FailingFile(real_fdopen(fd, *a, **k)))
    with pytest.raises(ConversationError, match="저장하지 못했다"):
        save_file(path, SAMPLE)  # 쓰는 도중 실패
    assert path.read_bytes() == before and [p.name for p in tmp_path.iterdir()] == ["chat.json"]

    real_unlink = os.unlink
    monkeypatch.setattr(conversation.os, "unlink", lambda p: (_ for _ in ()).throw(PermissionError(13, "Access is denied")))
    with pytest.raises(ConversationError, match="저장하지 못했다"):
        save_file(path, SAMPLE)  # 임시 파일을 지우지 못해도 원래 오류를 가리지 않는다
    assert path.read_bytes() == before
    monkeypatch.setattr(conversation.os, "unlink", real_unlink)
    for leftover in tmp_path.iterdir():
        if leftover.name != "chat.json":
            leftover.unlink()  # 정리 실패 시험이 남긴 임시 파일
