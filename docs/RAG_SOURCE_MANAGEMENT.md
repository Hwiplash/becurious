# RAG 출처 관리

## 기준 파일

RAG 검색의 최종 기준은 `data/rag_index/chunks.json`입니다. 원본과 전처리 결과는 출처군별로 다음 파일에서 관리합니다.

| 출처군 | 원본·관리 파일 | 전처리 결과 | 인덱스 청크 유형 |
|---|---|---|---|
| 정책·연구 PDF | `data/pdfs/`, `data/processed/catalog.json` | `data/processed/chunks.json` | `body`, `slide` |
| 지역 특산품 | 수집 PDF와 원문 URL | `data/processed/specialty_chunks.json` | `regional-specialty` |
| 업종분류 | `config/industry_taxonomy.json` | `data/processed/industry_taxonomy_chunks.json` | `industry-taxonomy` |

`outputs/source_catalog/지역외식산업_AI_출처관리대장.xlsx`는 위 파일과 실제 인덱스를 결합한 사람이 읽는 관리 대장입니다. 대장은 직접 수정하는 원본이 아니라 재생성 가능한 산출물입니다.

## 현재 범위

| 항목 | 수량 |
|---|---:|
| PDF 원본 | 248 |
| 정상 PDF | 247 |
| PDF 총 페이지 | 29,141 |
| 전체 RAG 청크 | 26,087 |
| 정책·연구 PDF 청크 | 24,355 |
| 지역 특산품 청크 | 1,721 |
| 업종분류 청크 | 11 |

수량은 2026-09-20 기준입니다. 이후에는 관리 대장의 `요약` 시트를 최신 값으로 봅니다.

## 갱신 순서

1. 원본 PDF 추가 후 `scripts/audit_pdfs.py`로 손상·중복·OCR 후보를 검사합니다.
2. `scripts/build_local_corpus.py`로 문서 목록과 청크를 갱신합니다.
3. 신규 정책 청크, 지역 특산품, 업종분류를 임베딩 인덱스에 추가합니다.
4. `scripts/build_source_catalog.mjs`로 출처 관리 대장을 재생성합니다.
5. `pytest`로 검색과 역할별 답변 회귀 테스트를 실행합니다.

전체 인덱스를 새로 만들 때는 `scripts/build_rag_index.py`를 사용합니다. 기존 인덱스에 추가할 때는 `scripts/append_specialties_to_rag.py --input <청크 JSON>`을 사용합니다. 이 스크립트 이름은 이전 특산품 전용 용도를 유지한 호환 이름이지만 현재는 모든 청크 유형을 처리합니다.

## 폴더 원칙

- `data/pdfs/`: 정책·연구 원본 PDF
- `data/processed/`: 재현 가능한 전처리 JSON
- `data/rag_index/`: 앱이 직접 읽는 검색 인덱스
- `data/qa/`: 감사 결과와 렌더링 미리보기
- `output/`: 크롤러·변환기의 재생성 가능한 중간 파일
- `outputs/`: 사람이 검수하거나 전달하는 최종 산출물
- `tmp/`: 일회성 임시 파일

대용량 데이터와 생성물은 Git 추적 여부가 다를 수 있으므로 파일 이동보다 이 경계를 유지하는 것을 우선합니다.
