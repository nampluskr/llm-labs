"""실제 pywebview 창을 띄워 DOM을 조작·관찰한다. 사용: python gui_driver.py <client> <host> <scenario> [entry]
시나리오: ok(두 질문) · stop(중단 버튼, 취소된 요청의 늦은 이벤트까지 관찰) · many(12번 연속 질문)
         · escape(HTML 이스케이프) · think·think_reopen(사고 과정 표시) · models(모델 전환·옵션) · bridge(브리지 없음·호출 거부) · late_reject(늦게 온 거부)
entry를 주면 build()가 아니라 앱 진입점 local_chat.app_<client>.main(argv)로 창을 띄운다.
결과를 JSON 한 줄로 stdout에 낸다. pytest(test_gui.py)가 서브프로세스로 돌린다."""

import importlib
import json
import sys
import time

import webview

from local_chat.clients import CLIENTS
from local_chat.webapp import build

LAST = "document.querySelector('.msg.assistant:last-of-type')"
SNAP = (
    "JSON.stringify({messages: document.querySelectorAll('.msg').length, input: document.getElementById('input').value, "
    "send_disabled: document.getElementById('send').disabled, stop_disabled: document.getElementById('stop').disabled, "
    "status: document.getElementById('status').textContent})"
)


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
            time.sleep(2.5)  # 취소된 첫 요청의 서버가 뒤늦게 토큰을 보내는 동안 창을 지켜본다
            late = state(window)
            result["late"] = {"final": late["t"], "status": late["status"], "send": late["send"], "stop": late["stop"],
                              "messages": js(window, "document.querySelectorAll('.msg').length")}
        elif scenario == "many":
            finals = []
            for i in range(1, 13):
                finals.append(ask(window, f"질문{i}")["status"])  # 종료 이벤트를 받은 즉시 다음 질문을 보낸다
                js(window, "document.getElementById('status').textContent = ''; 0")
            result["statuses"] = finals
        elif scenario == "bridge":
            wait(window, "document.getElementById('send').disabled === false", 10)
            # 1) 브리지가 없는 것처럼 만든다
            js(window, "window.__api = window.pywebview.api; window.pywebview.api = undefined; 0")
            submit(window, "질문")
            result["no_bridge"] = json.loads(js(window, SNAP))
            js(window, "window.pywebview.api = window.__api; 0")
            # 2) 호출이 거부(reject)되는 것처럼 만든다
            js(window, "window.__send = window.pywebview.api.send; window.pywebview.api.send = () => Promise.reject(new Error('x')); 0")
            submit(window, "질문")
            wait(window, "document.querySelectorAll('.msg').length === 0 && document.getElementById('send').disabled === false", 5)
            result["rejected"] = json.loads(js(window, SNAP))
            js(window, "window.pywebview.api.send = window.__send; 0")
            # 3) 복구한 뒤 정상으로 보낸다
            result["recovered"] = ask(window, "질문")
        elif scenario == "late_reject":
            wait(window, "document.getElementById('send').disabled === false", 10)
            # A: 브리지 호출이 늦게(0.9초 뒤) 거부된다. 그 사이 A의 턴이 끝난 것으로 처리(stopped)되고 B가 시작된다
            js(window, "window.__send = window.pywebview.api.send; window.pywebview.api.send = () => new Promise((_, rej) => setTimeout(() => rej(new Error('late')), 900)); 0")
            submit(window, "A")
            js(window, "window.onChatEvent({type: 'stopped'}); 0")  # 파이썬이 A를 중단했다고 알려 온 것처럼
            js(window, "window.pywebview.api.send = window.__send; 0")
            submit(window, "B")  # 실제 백엔드로 B를 보낸다(서버가 천천히 답한다)
            time.sleep(1.3)  # A의 거부가 B의 답변 도중에 도착한다
            mid = state(window)
            result["mid"] = {"t": mid["t"], "send": mid["send"], "stop": mid["stop"], "messages": js(window, "document.querySelectorAll('.msg').length")}
            wait(window, "document.getElementById('status').textContent.includes('tok/s')", 15)
            end_state = state(window)
            result["end"] = {"final": end_state["t"], "status": end_state["status"], "messages": js(window, "document.querySelectorAll('.msg').length")}
        elif scenario in ("think", "think_reopen"):
            probe = (
                "(function(){const b=" + LAST + ";const d=b.querySelector('details.think');"
                "const clone=b.cloneNode(true);const cd=clone.querySelector('details.think');if(cd)cd.remove();"
                "return JSON.stringify({det:!!d,open:d?d.open:null,summary:d?d.querySelector('summary').textContent:null,"
                "think:d?d.querySelector('.think-body').textContent:null,answer:clone.textContent,"
                "bold:b.querySelectorAll('b').length,status:document.getElementById('status').textContent})})()"
            )
            submit(window, "생각해 봐")
            seen, end = [], time.time() + 30
            while time.time() < end:
                st = json.loads(js(window, probe))
                key = (st["det"], st["open"], st["summary"], st["answer"] != "")
                if not seen or seen[-1][0] != key:
                    seen.append((key, st["think"], st["answer"]))

                if scenario == "think_reopen":
                    d = f"{LAST}.querySelector('details.think')"
                    if st["det"] and st["open"] and st["answer"] == "" and "closed_early" not in result:
                        js(window, f"{d}.open = false; 0")  # 생각하는 도중 사용자가 직접 닫는다
                        result["closed_early"] = True
                    elif st["answer"] != "" and result.get("closed_early") and "reopened_during" not in result:
                        js(window, f"{d}.open = true; 0")  # 답이 흐르는 도중에 다시 연다
                        result["reopened_during"] = True
                if st["status"]:
                    result["final"] = st
                    break
                time.sleep(0.02)
            result["seen"] = seen
            result["open_at_end"] = json.loads(js(window, probe))["open"]
            # 사용자가 접힌 블록을 다시 펼 수 있다
            js(window, f"{LAST}.querySelector('details.think').open = true; 0")
            result["reopened"] = json.loads(js(window, probe))["open"]
        elif scenario == "models":
            wait(window, "document.getElementById('model').disabled === false", 15)
            snap = (
                "JSON.stringify({status: document.getElementById('status').textContent, info: document.getElementById('info').textContent, "
                "model: document.getElementById('model').value, numctx: document.getElementById('numctx').value, "
                "temp: document.getElementById('temp').value, model_disabled: document.getElementById('model').disabled})"
            )

            def fire(selector, value=None):
                setter = "" if value is None else f"el.value = {json.dumps(value)}; "
                js(window, f"(function(){{const el = document.getElementById('{selector}'); {setter}el.dispatchEvent(new Event('change')); return 0}})()")

            def settle(text, timeout=10):
                return wait(window, f"document.getElementById('status').textContent.includes({json.dumps(text)})", timeout)

            result["options"] = json.loads(js(window, "JSON.stringify(Array.from(document.getElementById('model').options).map(o => ({value: o.value, text: o.textContent, disabled: o.disabled})))"))
            result["initial"] = json.loads(js(window, snap))
            # 모델 전환
            fire("model", "exaone3.5:7.8b")
            result["switched"] = settle("바꿨습니다")
            result["after_switch"] = json.loads(js(window, snap))
            # 채팅할 수 없는 모델(임베딩)을 억지로 고르면 거절되고 되돌아간다
            js(window, "document.getElementById('status').textContent = ''; 0")
            fire("model", "bge-m3:latest")
            settle("채팅할 수 없는")
            result["embedding"] = json.loads(js(window, snap))
            # 옵션 변경
            js(window, "document.getElementById('status').textContent = ''; 0")
            js(window, "document.getElementById('numctx').value = '8192'; document.getElementById('temp').value = '0.2'; 0")
            fire("numctx")
            result["options_set"] = settle("옵션을 바꿨습니다")
            result["after_options"] = json.loads(js(window, snap))
            result["ask"] = ask(window, "질문")
            # 범위 밖 num_ctx는 거절되고 입력이 되돌아간다
            js(window, "document.getElementById('status').textContent = ''; 0")
            fire("numctx", "9000")
            settle("4096~8192")
            result["out_of_range"] = json.loads(js(window, snap))
            # 빈 temperature를 0으로 읽지 않는다
            js(window, "document.getElementById('status').textContent = ''; 0")
            fire("temp", "")
            settle("temperature")
            result["empty_temp"] = json.loads(js(window, snap))
            # 답변 중에는 모델·옵션 입력이 잠긴다
            submit(window, "느린 질문")
            locked, end = [], time.time() + 30
            while time.time() < end:
                st = json.loads(js(window, "JSON.stringify({busy: !document.getElementById('stop').disabled, model: document.getElementById('model').disabled, numctx: document.getElementById('numctx').disabled, temp: document.getElementById('temp').disabled, status: document.getElementById('status').textContent})"))
                if st["busy"]:
                    locked.append((st["model"], st["numctx"], st["temp"]))
                if st["status"]:
                    break
                time.sleep(0.02)
            result["locked_while_busy"] = sorted(set(locked))
            result["after_busy"] = json.loads(js(window, "JSON.stringify({model: document.getElementById('model').disabled, numctx: document.getElementById('numctx').disabled, temp: document.getElementById('temp').disabled})"))
        elif scenario == "switch_lock":
            wait(window, "document.getElementById('model').disabled === false", 15)
            probe = (
                "JSON.stringify({model: document.getElementById('model').disabled, numctx: document.getElementById('numctx').disabled, "
                "temp: document.getElementById('temp').disabled, send: document.getElementById('send').disabled, "
                "status: document.getElementById('status').textContent, info: document.getElementById('info').textContent})"
            )
            js(window, "(function(){const el = document.getElementById('model'); el.value = 'exaone3.5:7.8b'; el.dispatchEvent(new Event('change')); return 0})()")
            seen, end = [], time.time() + 20
            submitted = False
            while time.time() < end:
                st = json.loads(js(window, probe))
                if "바꿨습니다" in st["status"]:
                    break
                seen.append((st["model"], st["numctx"], st["temp"], st["send"]))
                if not submitted and st["send"]:
                    submit(window, "전환 중 질문")  # 잠긴 동안 보내려 해 본다
                    submitted = True
                time.sleep(0.05)
            result["locked_during_switch"] = sorted(set(seen))
            result["submitted_during_switch"] = submitted
            result["bubbles_after_switch"] = js(window, "document.querySelectorAll('.msg').length")
            result["after"] = json.loads(js(window, probe))
        elif scenario == "escape":
            result["first"] = ask(window, "태그")
            result["bold_elements"] = js(window, "document.querySelectorAll('.msg.assistant b').length")
    except Exception as e:  # 관찰 실패도 결과로 남긴다
        result["driver_error"] = repr(e)
    finally:
        window.destroy()


if __name__ == "__main__":
    client_name, host, scenario = sys.argv[1:4]
    entry = len(sys.argv) > 4 and sys.argv[4] == "entry"
    result = {}
    if entry:
        # 앱 진입점 main(argv)이 argparse → build → webview.start까지 실제로 돌게 하고, start만 감싸 창을 조작한다
        module = importlib.import_module(f"local_chat.app_{client_name}")
        real_start = webview.start
        webview.start = lambda: real_start(drive, (webview.windows[0], result, scenario))
        module.main(["--host", host, "--model", "qwen3:4b"])
    else:
        window, api = build(CLIENTS[client_name](host=host))
        webview.start(drive, (window, result, scenario))
    print("RESULT " + json.dumps(result))
