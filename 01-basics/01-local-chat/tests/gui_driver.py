"""실제 pywebview 창을 띄워 DOM을 조작·관찰한다. 사용: python gui_driver.py <client> <host> <scenario>
시나리오: ok(두 질문) · stop(중단 버튼) · many(12번 연속 질문) · escape(HTML 이스케이프)
결과를 JSON 한 줄로 stdout에 낸다. pytest(test_gui.py)가 서브프로세스로 돌린다."""

import json
import sys
import time

import webview

from local_chat.clients import CLIENTS
from local_chat.webapp import build

LAST = "document.querySelector('.msg.assistant:last-of-type')"


def js(window, code):
    return window.evaluate_js(code)


def wait(window, cond, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        if js(window, cond):
            return True
        time.sleep(0.03)
    return False


def state(window):
    return json.loads(
        js(
            window,
            f"JSON.stringify({{t: {LAST}.textContent, html: {LAST}.innerHTML, "
            "send: document.getElementById('send').disabled, stop: document.getElementById('stop').disabled, "
            "status: document.getElementById('status').textContent})",
        )
    )


def submit(window, text):
    js(window, f"document.getElementById('input').value = {json.dumps(text)}; document.getElementById('send').click(); 0")


def ask(window, text):
    """질문을 보내고 답이 끝날 때까지 답변 말풍선의 글자 수 변화를 기록한다."""
    submit(window, text)
    samples, buttons = [], []
    end = time.time() + 30
    while time.time() < end:
        st = state(window)
        if not samples or samples[-1] != st["t"]:
            samples.append(st["t"])
        buttons.append((st["send"], st["stop"]))
        if st["status"]:
            return {"samples": samples, "buttons": buttons, "status": st["status"], "final": st["t"], "html": st["html"]}
        time.sleep(0.02)
    return {"samples": samples, "buttons": buttons, "status": None, "final": samples[-1] if samples else None}


def drive(window, result, scenario):
    try:
        result["ready"] = wait(window, "document.getElementById('info').textContent.length > 0", 20)
        result["title"] = js(window, "document.getElementById('title').textContent")
        result["info"] = js(window, "document.getElementById('info').textContent")
        if scenario == "ok":
            result["first"] = ask(window, "안녕")
            result["after_ready_to_send"] = js(window, "document.getElementById('send').disabled === false && document.getElementById('input').value === ''")
            result["second"] = ask(window, "또 질문")
            result["messages"] = js(window, "document.querySelectorAll('.msg').length")
        elif scenario == "stop":
            submit(window, "멈출 질문")
            result["got_token"] = wait(window, f"{LAST} && {LAST}.textContent.length > 0", 15)
            before = state(window)
            result["before"] = {"send": before["send"], "stop": before["stop"]}
            t0 = time.time()
            js(window, "document.getElementById('stop').click(); 0")
            result["stopped"] = wait(window, "document.getElementById('status').textContent.includes('중단')", 5)
            result["stop_seconds"] = round(time.time() - t0, 2)
            after = state(window)
            result["after"] = {"send": after["send"], "stop": after["stop"], "status": after["status"]}
            result["next"] = ask(window, "다음 질문")  # 서버가 멈춰 있어도 새 질문이 나간다
            result["messages"] = js(window, "document.querySelectorAll('.msg').length")
        elif scenario == "many":
            finals = []
            for i in range(1, 13):
                finals.append(ask(window, f"질문{i}")["status"])
                js(window, "document.getElementById('status').textContent = ''; 0")
            result["statuses"] = finals
        elif scenario == "escape":
            result["first"] = ask(window, "태그")
            result["bold_elements"] = js(window, "document.querySelectorAll('.msg.assistant b').length")
    except Exception as e:  # 관찰 실패도 결과로 남긴다
        result["driver_error"] = repr(e)
    finally:
        window.destroy()


if __name__ == "__main__":
    client_name, host, scenario = sys.argv[1:4]
    result = {}
    window, api = build(CLIENTS[client_name](host=host))
    webview.start(drive, (window, result, scenario))
    print("RESULT " + json.dumps(result))
