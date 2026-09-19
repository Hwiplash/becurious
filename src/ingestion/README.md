# Ingestion package

이 폴더는 50개 안팎의 이질적인 정책·연구 PDF를 자동 처리하기 위한 확장 지점입니다.

예정 모듈 책임은 다음과 같습니다.

- `profiler.py`: 문서·페이지 유형과 OCR 필요 여부 판정
- `extractor.py`: PyMuPDF 텍스트 추출 및 선택적 OCR
- `chunker.py`: 슬라이드 페이지 단위/보고서 제목 단위 청킹
- `metadata.py`: 표지·목차·결론을 이용한 문서 메타데이터 생성
- `case_extractor.py`: 정책·사례 후보 청크의 구조화 카드 생성
- `validator.py`: 누락·깨진 문자·중복·저신뢰 문서 검수
- `models.py`: 파이프라인 공통 데이터 구조

현재 앱에서 사용하는 `scripts/build_rag_index.py`는 단순 페이지 기반 인덱서입니다. 위 모듈 구현이 끝나기 전까지는 두 방식을 혼동하지 않도록 기존 스크립트를 유지합니다.

