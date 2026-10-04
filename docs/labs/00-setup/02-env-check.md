> 버전: v0.1 · 작성일: 2026-10-04

# 00-02 env-check — 개발 환경 확인과 점검 CLI

## 1. 개요

연습을 시작하기 전에 파이썬 개발 환경(uv, pywebview, jupyter)이 동작하는지 확인하고, Ollama·받은
모델·GPU 적재 상태를 한 번에 점검하는 파이썬 CLI를 만든다. 00-01에서 사람이 손으로 확인하던 것의
일부를 반복 실행할 수 있게 한 것이다. 연습 폴더마다 `pyproject.toml`을 두므로(저장소 DECISIONS R-10)
환경 확인도 이 연습의 환경에서 한다.

- uv로 연습별 환경 만들기
- pywebview 창과 jupyter 커널이 실제로 뜨는지 확인
- Ollama 서버 연결, 모델 목록, 적재 상태를 API로 확인

## 2. 기술 스택

| 항목 | 내용 |
| --- | --- |
| 런타임 | Python CLI(화면 없음) |
| 언어·패키지 | Python 3.13(uv), `ollama`, `pywebview`(동작 확인용), `jupyter`·`ipykernel`(동작 확인용), argparse |
| Ollama API | `/api/tags`, `/api/ps`, `/api/version` |
| 모델 | 받은 모델 전부(확인 대상) |
| num_ctx | 해당 없음 |

## 3. 간단한 플랜

| Phase | 목적 | 완료 조건 |
| --- | --- | --- |
| 1 | 파이썬 환경 | 이 연습 폴더에서 `uv sync`가 끝나고, pywebview 창이 뜨며, jupyter 커널로 셀 한 개가 실행된다 |
| 2 | Ollama 점검 | `env-check`가 Ollama 서버 연결·버전·받은 모델 목록·적재된 모델과 PROCESSOR를 출력하고, 서버를 껐을 때는 오류 문구와 종료 코드 1을 낸다 |
| 3 | 요약 출력 | 점검 항목마다 통과/실패 한 줄과 전체 결과를 출력하고, `--json`으로 같은 내용을 JSON으로 낸다 |

## 4. 하드웨어 메모

- 점검은 읽기 전용 API만 쓰므로 VRAM을 추가로 쓰지 않는다.
- 이미 적재된 모델이 있을 때 점검 결과의 PROCESSOR가 평상시 점유(약 1.8GB)와 섞이지 않게, 모델 적재는 하지 않고 현재 상태만 읽는다.

## 5. 미정

- 점검할 항목의 최종 목록(예: `nvidia-smi` VRAM, 드라이버 버전, 디스크 여유)
- 점검 결과를 파일로 남길지 여부
