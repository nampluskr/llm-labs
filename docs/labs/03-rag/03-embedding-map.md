> 버전: v0.1 · 작성일: 2026-10-04

# 03-03 embedding-map — 문서 임베딩 2D 지도

## 1. 개요

문서(또는 청크) 임베딩을 PCA·t-SNE·UMAP으로 2D에 투영하고, k-means로 군집을 나눠 Plotly
산점도로 보여 주는 앱이다. 점에 마우스를 올리면 제목·미리보기, 군집마다 LLM이 붙인 이름이 보인다.
사용자에게 익숙한 scikit-learn·Plotly 작업에 임베딩을 입력으로 쓰는 연습이다.

- 고차원 임베딩의 차원 축소와 그 한계
- 군집 결과에 LLM으로 이름 붙이기
- 03-01·03-02의 색인 파일 재사용

## 2. 기술 스택

| 항목 | 내용 |
| --- | --- |
| 런타임 | Python + pywebview(Plotly.js) |
| 언어·패키지 | Python 3.13(uv), `ollama`, `numpy`, `scikit-learn`, `umap-learn`, `pywebview` |
| Ollama API | `/api/embed`, `/api/generate`(군집 이름) |
| 모델 | `bge-m3`, `qwen3:4b` |
| num_ctx | 4096 |

## 3. 간단한 플랜

| Phase | 목적 | 완료 조건 |
| --- | --- | --- |
| 1 | 투영 | 색인 파일을 읽어 PCA·t-SNE·UMAP 2D 좌표를 계산하고 방법별 소요 시간을 출력한다 |
| 2 | 지도 | 산점도에서 방법을 전환할 수 있고, 점 hover에 출처와 앞 100자가 보인다 |
| 3 | 군집 이름 | k-means k개 군집마다 대표 청크 5개로 LLM이 붙인 이름이 범례에 표시된다 |

## 4. 하드웨어 메모

- 차원 축소는 CPU(scikit-learn)로 한다. 수천 점은 수 초~수십 초로 예상한다.
- LLM은 군집 이름 붙이기에만 짧게 쓰므로 `qwen3:4b`로 충분하다.

## 5. 미정

없음
