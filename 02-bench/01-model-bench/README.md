# 02-01 model-bench

## 개요

Ollama로 받아 둔 모델 전부에 같은 프롬프트를 돌려, 이 PC(GTX 1080 Ti 11GB)에서 모델별 생성 속도(tok/s)와 VRAM 사용량을 재고 표와 차트로 보여 주는 pywebview 앱이다. 어떤 모델이 이 PC에서 쓸 만한지 숫자로 알고, 이후 연습에서 쓸 모델을 고르는 근거로 삼는 것이 목적이다.

모델마다 프롬프트 3개 × 반복 3회를 `num_ctx` 4096으로 측정한다. VRAM을 넘는 MoE 모델 `qwen3:30b`도 포함해 GPU/CPU 비율(PROCESSOR)을 함께 기록한다. 결과는 CSV로 저장되고, 화면에서 모델별 tok/s·VRAM 표와 차트로 볼 수 있다. 품질 평가는 하지 않고 속도·VRAM 실측만 한다.

이 연습은 저장소 `llm-labs`의 연습 하나이며, 저장소의 의도는 저장소 루트의 `docs/INTENT.md`에 있다.
