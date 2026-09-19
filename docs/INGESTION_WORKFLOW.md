# PDF RAG 구축 작업 순서

## 완성 목표

사용자는 `data/pdfs/`에 PDF를 넣고 한 번의 명령으로 다음 결과를 생성한다.

```text
data/processed/catalog.json
data/processed/chunks.json
data/processed/case_cards.json
data/qa/ingestion_report.csv
data/rag_index/embeddings.npy
data/rag_index/manifest.json
```

## 파이프라인

```text
PDF 수집
→ 파일 해시·중복 검사
→ 문서/페이지 프로파일링
→ 텍스트 추출과 선택적 OCR
→ 슬라이드/보고서 유형별 청킹
→ 문서 메타데이터 자동 추출
→ 정책·사례 카드 추출
→ 품질검수 리포트
→ 임베딩과 로컬 인덱스
```

## 구현 순서

1. `profiler.py`: 가로형 비율, 텍스트 길이, 이미지 수로 페이지 유형을 판정한다.
2. `extractor.py`: 텍스트가 150자 미만인 이미지 페이지에만 OCR을 실행한다.
3. `chunker.py`: 슬라이드는 페이지 하나, 보고서는 제목·절 단위로 청킹한다.
4. `metadata.py`: 표지·목차·결론 일부를 이용해 제목, 연도, 기관, 지역, 주제를 JSON으로 생성한다.
5. `case_extractor.py`: 사례·정책·전략 키워드가 있는 청크만 LLM으로 구조화한다.
6. `validator.py`: 저신뢰 문서와 추출 실패 문서만 검수 대상으로 표시한다.
7. 기존 `build_rag_index.py`를 위 모듈을 호출하는 오케스트레이터로 교체한다.
8. `src/rag.py`에 키워드 점수와 메타데이터 점수를 추가한다.

## 품질 기준

- 모든 청크에 문서명과 페이지가 있어야 한다.
- 실제 시행 사례와 연구 제안을 구분해야 한다.
- 원문에 없는 예산·성과 수치를 만들지 않는다.
- 발행연도가 없거나 신뢰도가 낮으면 검수 대상으로 보낸다.
- 같은 파일 해시는 다시 처리하지 않는다.
- 답변에는 최종적으로 사용된 원문 청크만 인용한다.

