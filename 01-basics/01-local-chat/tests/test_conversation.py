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
    save_file(path, [u("가" * 2000), a("답")])
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
