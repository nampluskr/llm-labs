"""실제 pywebview 창을 띄워 DOM을 조작·관찰한다. 사용: python gui_driver.py <client> <host> <scenario> [entry]
시나리오: ok(두 질문) · stop(중단 버튼, 취소된 요청의 늦은 이벤트까지 관찰) · many(12번 연속 질문)
         · escape(HTML 이스케이프) · think·think_reopen(사고 과정 표시) · models(모델 전환·옵션) · save·load·load_corrupt·load_over·load_lost·load_early_lost·dialog_save·dialog_open·dialog_cancel(대화 저장·열기. dialog_*는 실제 네이티브 파일 대화상자) · desync·load_never_settles·load_many·load_delayed · bridge(브리지 없음·호출 거부) · late_reject(늦게 온 거부)
entry를 주면 build()가 아니라 앱 진입점 local_chat.app_<client>.main(argv)로 창을 띄운다.
결과를 JSON 한 줄로 stdout에 낸다. pytest(test_gui.py)가 서브프로세스로 돌린다."""

import importlib
import json
import os
import sys
import time

import webview

from local_chat.clients import CLIENTS
from local_chat.webapp import build

LAST = "document.querySelector('.msg.assistant:last-of-type')"
API = None  # build()로 띄운 경우의 Api. 화면이 모르게 서버의 대화를 바꾸는 시나리오(desync)에서 쓴다


def _dialog_helper():
    """실제 파일 대화상자(공용 대화상자, 클래스 #32770)를 Windows API로 조작한다. Windows 전용."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    WM_SETTEXT, WM_COMMAND, WM_CLOSE = 0x000C, 0x0111, 0x0010
    enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def class_name(hwnd):
        buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buf, 256)
        return buf.value

    def find_dialog(timeout):
        end = time.time() + timeout
        while time.time() < end:
            found = []

            def cb(hwnd, _):
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value == os.getpid() and user32.IsWindowVisible(hwnd) and class_name(hwnd) == "#32770":
                    found.append(hwnd)
                return True

            user32.EnumWindows(enum_proc(cb), 0)
            if found:
                return found[0]
            time.sleep(0.1)
        return None

    def children(hwnd):
        out = []

        def cb(h, _):
            out.append((h, class_name(h)))
            return True

        user32.EnumChildWindows(hwnd, enum_proc(cb), 0)
        return out

    def act(path, log):
        """대화상자가 뜨기를 기다렸다가 path를 입력하고 확인을 누른다. path가 None이면 닫는다(취소)."""
        dlg = find_dialog(20)
        log.append(bool(dlg))
        if not dlg:
            return
        time.sleep(0.5)
        if path is None:
            user32.PostMessageW(dlg, WM_CLOSE, 0, 0)
            return
        edits = [h for h, c in children(dlg) if c == "Edit"]  # 파일 이름 입력칸
        user32.SendMessageW(edits[0], WM_SETTEXT, 0, path)
        time.sleep(0.3)
        user32.PostMessageW(dlg, WM_COMMAND, 1, user32.GetDlgItem(dlg, 1))  # 저장·열기 버튼(ID 1)

    return act


def automate_dialog(path, log):
    """백그라운드 스레드로 다음에 열릴 대화상자를 조작한다."""
    import threading

    thread = threading.Thread(target=_dialog_helper(), args=(path, log), daemon=True)
    thread.start()
    return thread

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
        elif scenario == "switch_lost":
            wait(window, "document.getElementById('model').disabled === false", 15)
            # 서버에서는 전환이 성공하지만 응답이 화면에 도착하지 못한 것처럼 만든다
            js(window, "window.__setModel = window.pywebview.api.set_model; window.pywebview.api.set_model = async (n) => { await window.__setModel(n); throw new Error('lost'); }; 0")
            js(window, "(function(){const el = document.getElementById('model'); el.value = 'exaone3.5:7.8b'; el.dispatchEvent(new Event('change')); return 0})()")
            wait(window, "document.getElementById('model').disabled === false && document.getElementById('status').textContent.length > 0", 15)
            result["after"] = json.loads(js(window, "JSON.stringify({model: document.getElementById('model').value, info: document.getElementById('info').textContent, status: document.getElementById('status').textContent, send: document.getElementById('send').disabled})"))
            result["ask"] = ask(window, "질문")
        elif scenario == "switch_blind":
            wait(window, "document.getElementById('model').disabled === false", 15)
            # 서버에서는 전환이 성공하지만, 그 응답도 뒤따르는 상태 조회(info)도 화면에 도착하지 못하는 것처럼 만든다
            js(window, "window.__setModel = window.pywebview.api.set_model; window.pywebview.api.set_model = async (n) => { await window.__setModel(n); throw new Error('lost'); }; window.pywebview.api.info = async () => { throw new Error('lost'); }; 0")
            js(window, "(function(){const el = document.getElementById('model'); el.value = 'exaone3.5:7.8b'; el.dispatchEvent(new Event('change')); return 0})()")
            wait(window, "document.getElementById('status').textContent.length > 0", 15)
            time.sleep(0.5)
            result["after"] = json.loads(js(window, "JSON.stringify({status: document.getElementById('status').textContent, send: document.getElementById('send').disabled, model: document.getElementById('model').disabled, numctx: document.getElementById('numctx').disabled})"))
            submit(window, "화면과 다른 모델로 가면 안 되는 질문")
            time.sleep(0.5)
            result["bubbles"] = js(window, "document.querySelectorAll('.msg').length")
        elif scenario == "switch_midflight":
            wait(window, "document.getElementById('model').disabled === false", 15)
            # 서버의 전환은 진행 중인데 브리지 응답만 먼저 실패하는 것처럼 만든다(전환은 내리기가 실패해 되돌려질 것이다)
            js(window, "window.__setModel = window.pywebview.api.set_model; window.pywebview.api.set_model = (n) => { window.__setModel(n); return Promise.reject(new Error('lost')); }; 0")
            js(window, "(function(){const el = document.getElementById('model'); el.value = 'exaone3.5:7.8b'; el.dispatchEvent(new Event('change')); return 0})()")
            time.sleep(0.5)  # 서버가 아직 내리는 중이다
            result["during"] = json.loads(js(window, "JSON.stringify({send: document.getElementById('send').disabled, model: document.getElementById('model').disabled, info: document.getElementById('info').textContent})"))
            wait(window, "!document.getElementById('send').disabled", 30)
            result["after"] = json.loads(js(window, "JSON.stringify({model: document.getElementById('model').value, info: document.getElementById('info').textContent, send: document.getElementById('send').disabled})"))
            result["ask"] = ask(window, "질문")
        elif scenario == "double_change":
            wait(window, "document.getElementById('model').disabled === false", 15)
            fire_js = "(function(id, v){const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('change')); return 0})"
            js(window, fire_js + "('model', 'exaone3.5:7.8b')")  # 첫 변경이 처리되는 동안
            js(window, fire_js + "('model', 'qwen3:14b')")  # 두 번째 변경 이벤트가 온다
            js(window, fire_js + "('numctx', '8192')")  # 옵션 변경도 온다
            wait(window, "document.getElementById('model').disabled === false", 30)
            time.sleep(0.3)
            result["after"] = json.loads(js(window, "JSON.stringify({model: document.getElementById('model').value, numctx: document.getElementById('numctx').value, info: document.getElementById('info').textContent})"))
            result["ask"] = ask(window, "질문")
        elif scenario in ("desync", "load_never_settles", "load_many", "load_delayed"):
            wait(window, "document.getElementById('save').disabled === false", 15)
            bubbles = "JSON.stringify(Array.from(document.querySelectorAll('.msg')).map(m => [m.classList.contains('user') ? 'user' : 'assistant', m.textContent]))"
            pick = os.environ["GUI_DRIVER_PICK"]
            if scenario == "desync":
                ask(window, "화면에 있던 질문")
                result["server"] = API._load_from(pick)["count"]  # 화면이 모르게 서버의 대화가 파일의 대화로 바뀐다(열기 응답이 화면에 도착하지 못한 것과 같다)
                result["before"] = json.loads(js(window, bubbles))
                js(window, "document.getElementById('input').value = '어긋난 채 보낸 질문'; document.getElementById('send').click(); 0")
                wait(window, "document.getElementById('status').textContent.includes('다시 그렸습니다')", 15)
                time.sleep(0.3)
                result["status"] = js(window, "document.getElementById('status').textContent")
                result["after"] = json.loads(js(window, bubbles))
                result["input"] = js(window, "document.getElementById('input').value")
                result["controls"] = json.loads(js(window, "JSON.stringify({send: document.getElementById('send').disabled, open: document.getElementById('open').disabled})"))
                result["resent"] = ask(window, "어긋난 채 보낸 질문")  # 같은 질문을 다시 보낸다
            elif scenario == "load_delayed":
                ask(window, "화면에 있던 질문")
                # 열기 요청이 서버에 늦게(2.5초 뒤) 도착하는데 브리지 약속은 바로 실패하는 것처럼 만든다.
                # 복구 시점에는 서버가 놀고 있으므로 화면은 옛 대화로 풀리고, 그 뒤 열기가 처리된다
                js(window, "window.__load = window.pywebview.api.load_chat; window.pywebview.api.load_chat = () => { setTimeout(() => window.__load(), 2500); return Promise.reject(new Error('lost')); }; 0")
                js(window, "document.getElementById('status').textContent = ''; document.getElementById('open').click(); 0")
                time.sleep(1.8)
                result["early"] = json.loads(js(window, bubbles))  # 복구 직후: 아직 옛 대화
                result["early_status"] = js(window, "document.getElementById('status').textContent")
                result["caught_up"] = wait(window, "document.getElementById('status').textContent.includes('뒤늦게 처리된 열기')", 30)
                result["bubbles"] = json.loads(js(window, bubbles))
                result["controls"] = json.loads(js(window, "JSON.stringify({send: document.getElementById('send').disabled, open: document.getElementById('open').disabled})"))
                result["next"] = ask(window, "넷째 질문")
            elif scenario == "load_never_settles":
                ask(window, "화면에 있던 질문")
                # 서버의 열기는 끝나는데 브리지 응답이 영영 오지 않는 것처럼 만든다(약속이 끝나지 않는다)
                js(window, "window.__load = window.pywebview.api.load_chat; window.pywebview.api.load_chat = () => { window.__load(); return new Promise(() => {}); }; 0")
                js(window, "document.getElementById('status').textContent = ''; document.getElementById('open').click(); 0")
                t0 = time.time()
                result["recovered"] = wait(window, "document.getElementById('status').textContent.includes('서버의 대화로 화면을 맞췄습니다')", 40)
                result["seconds"] = round(time.time() - t0, 1)
                result["bubbles"] = json.loads(js(window, bubbles))
                result["controls"] = json.loads(js(window, "JSON.stringify({send: document.getElementById('send').disabled, open: document.getElementById('open').disabled})"))
                result["next"] = ask(window, "넷째 질문")  # 복구한 뒤 버전이 맞아 질문이 나간다
            else:
                js(window, "document.getElementById('status').textContent = ''; document.getElementById('open').click(); 0")
                t0 = time.time()
                result["done"] = wait(window, "document.getElementById('status').textContent.includes('불러왔습니다')", 60)
                result["seconds"] = round(time.time() - t0, 1)
                result["count"] = js(window, "document.querySelectorAll('.msg').length")
                result["first_last"] = json.loads(js(window, "JSON.stringify([document.querySelector('.msg:first-child').textContent, document.querySelector('.msg:last-child').textContent])"))
                result["alive"] = js(window, "1 + 1")  # 화면이 응답한다
        elif scenario in ("dialog_save", "dialog_open", "dialog_cancel"):
            wait(window, "document.getElementById('save').disabled === false", 15)
            bubbles = "JSON.stringify(Array.from(document.querySelectorAll('.msg')).map(m => [m.classList.contains('user') ? 'user' : 'assistant', m.textContent]))"
            chosen = os.environ["GUI_DRIVER_DIALOG_PATH"]
            log = []
            if scenario == "dialog_save":
                ask(window, "첫째 질문 😊")
                ask(window, "둘째\n질문")
                automate_dialog(chosen, log)
                js(window, "document.getElementById('status').textContent = ''; document.getElementById('save').click(); 0")
                result["saved"] = wait(window, "document.getElementById('status').textContent.includes('저장')", 30)
                result["status"] = js(window, "document.getElementById('status').textContent")
            elif scenario == "dialog_open":
                automate_dialog(chosen, log)
                js(window, "document.getElementById('status').textContent = ''; document.getElementById('open').click(); 0")
                wait(window, "document.getElementById('status').textContent.length > 0", 30)
                time.sleep(0.3)
                result["status"] = js(window, "document.getElementById('status').textContent")
                result["bubbles"] = json.loads(js(window, bubbles))
                result["next"] = ask(window, "넷째 질문")
            else:
                ask(window, "지켜야 할 질문")
                before = json.loads(js(window, bubbles))
                statuses = []
                for button in ("save", "open"):
                    automate_dialog(None, log)  # 대화상자를 취소한다
                    js(window, f"document.getElementById('status').textContent = ''; document.getElementById('{button}').click(); 0")
                    wait(window, "document.getElementById('status').textContent.length > 0", 30)
                    statuses.append(js(window, "document.getElementById('status').textContent"))
                time.sleep(0.3)
                result["statuses"] = statuses
                result["before"] = before
                result["bubbles"] = json.loads(js(window, bubbles))
                result["controls"] = json.loads(js(window, "JSON.stringify({send: document.getElementById('send').disabled, save: document.getElementById('save').disabled, open: document.getElementById('open').disabled})"))
            result["dialog_seen"] = log
        elif scenario == "load_early_lost":
            wait(window, "document.getElementById('save').disabled === false", 15)
            bubbles = "JSON.stringify(Array.from(document.querySelectorAll('.msg')).map(m => [m.classList.contains('user') ? 'user' : 'assistant', m.textContent]))"
            ask(window, "화면에 있던 질문")
            # 서버의 열기는 아직 진행 중(대화상자 대기)인데 브리지 응답만 먼저 실패하는 것처럼 만든다
            js(window, "window.__load = window.pywebview.api.load_chat; window.pywebview.api.load_chat = () => { window.__load(); return Promise.reject(new Error('lost')); }; 0")
            js(window, "document.getElementById('status').textContent = ''; document.getElementById('open').click(); 0")
            time.sleep(0.6)  # 서버는 아직 파일을 고르는 중이다
            result["during"] = json.loads(js(window, "JSON.stringify({send: document.getElementById('send').disabled, open: document.getElementById('open').disabled, save: document.getElementById('save').disabled, status: document.getElementById('status').textContent, bubbles: Array.from(document.querySelectorAll('.msg')).map(m => m.textContent)})"))
            wait(window, "!document.getElementById('send').disabled", 30)
            time.sleep(0.3)
            result["status"] = js(window, "document.getElementById('status').textContent")
            result["bubbles"] = json.loads(js(window, bubbles))
            result["next"] = ask(window, "넷째 질문")
        elif scenario in ("load_over", "load_lost"):
            wait(window, "document.getElementById('save').disabled === false", 15)
            bubbles = "JSON.stringify(Array.from(document.querySelectorAll('.msg')).map(m => [m.classList.contains('user') ? 'user' : 'assistant', m.textContent]))"
            result["asked"] = ask(window, "화면에 있던 질문")  # 사고 과정 블록이 있는 대화가 화면에 있다
            result["think_blocks_before"] = js(window, "document.querySelectorAll('details.think').length")
            if scenario == "load_lost":
                # 서버에서는 열기가 성공하지만 응답이 화면에 도착하지 못한 것처럼 만든다
                js(window, "window.__load = window.pywebview.api.load_chat; window.pywebview.api.load_chat = async () => { await window.__load(); throw new Error('lost'); }; 0")
            js(window, "document.getElementById('status').textContent = ''; document.getElementById('open').click(); 0")
            wait(window, "document.getElementById('status').textContent.length > 0", 15)
            time.sleep(0.8)
            result["status"] = js(window, "document.getElementById('status').textContent")
            result["bubbles"] = json.loads(js(window, bubbles))
            result["think_blocks_after"] = js(window, "document.querySelectorAll('details.think').length")
            result["controls"] = json.loads(js(window, "JSON.stringify({send: document.getElementById('send').disabled, open: document.getElementById('open').disabled})"))
        elif scenario in ("save", "load", "load_corrupt"):
            wait(window, "document.getElementById('save').disabled === false", 15)
            bubbles = "JSON.stringify(Array.from(document.querySelectorAll('.msg')).map(m => [m.classList.contains('user') ? 'user' : 'assistant', m.textContent]))"
            if scenario == "save":
                ask(window, "첫째 질문 😊")
                ask(window, "둘째\n질문")
                js(window, "document.getElementById('status').textContent = ''; document.getElementById('save').click(); 0")
                result["saved"] = wait(window, "document.getElementById('status').textContent.includes('저장')", 15)
                result["status"] = js(window, "document.getElementById('status').textContent")
                result["bubbles"] = json.loads(js(window, bubbles))
            else:
                if scenario == "load_corrupt":
                    ask(window, "지켜야 할 질문")  # 화면에 대화가 있는 상태에서 손상된 파일을 연다
                result["before"] = json.loads(js(window, bubbles))
                js(window, "document.getElementById('status').textContent = ''; document.getElementById('open').click(); 0")
                wait(window, "document.getElementById('status').textContent.length > 0", 15)
                time.sleep(0.3)
                result["status"] = js(window, "document.getElementById('status').textContent")
                result["bubbles"] = json.loads(js(window, bubbles))
                result["controls"] = json.loads(js(window, "JSON.stringify({send: document.getElementById('send').disabled, save: document.getElementById('save').disabled, open: document.getElementById('open').disabled})"))
                result["next"] = ask(window, "넷째 질문")
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
        API = api
        pick = os.environ.get("GUI_DRIVER_PICK")
        if pick:  # 파일 대화상자 대신 시험이 정한 경로를 쓴다
            delay = float(os.environ.get("GUI_DRIVER_PICK_DELAY", "0"))  # 주면 경로를 고르는 데 그만큼 걸린다(느린 대화상자)
            api._pick_path = lambda mode: (time.sleep(delay), pick)[1]
        webview.start(drive, (window, result, scenario))
    print("RESULT " + json.dumps(result))
