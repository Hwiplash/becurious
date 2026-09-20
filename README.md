# ABP 상권 인사이트 및 정책 제안 에이전트

BC카드 공모전 소비 집계 데이터를 전국 → 시도 → 시군구 단위로 탐색하고, 지역별 Pain Point·Advantage와 PDF 사례를 결합해 정책을 제안하는 Streamlit 앱입니다.

## 실행

```powershell
scripts\setup.ps1
..\.venv\Scripts\python.exe -m streamlit run app.py
```

`.env`의 `OPENAI_API_KEY`를 설정하면 AI 정책 제안 기능이 활성화됩니다. 기본 조합은 Small 임베딩과 Luna 근거 재정렬·최종 제안입니다.

## RAG 출처와 갱신

RAG는 세 종류의 근거를 함께 검색합니다.

- 정책·연구 PDF: 지역경제, 외식산업, 상권 및 정책 사례
- 지역 특산품: 특산품의 특징과 제공되는 활용 음식
- 업종분류: 11개 표준 업종 코드와 검색 별칭

현재 인덱스에는 총 26,087개 청크가 있으며 정책·연구 PDF 24,355개, 지역 특산품 1,721개, 업종분류 11개입니다. 실제 검색에 포함된 전체 출처는 `outputs/source_catalog/지역외식산업_AI_출처관리대장.xlsx`에서 확인합니다.

### 정책 PDF 갱신

1. 정책·상권 사례 PDF를 `data/pdfs/`에 넣습니다.
2. 출처 상태와 중복·OCR 필요 문서를 점검합니다.

```powershell
..\.venv\Scripts\python.exe scripts\audit_pdfs.py
```

3. PDF를 문서 목록, 검색 조각, 사례 카드로 변환합니다.

```powershell
..\.venv\Scripts\python.exe scripts\build_local_corpus.py
```

이 상태만으로도 앱의 로컬 근거 검색이 작동합니다. `OPENAI_API_KEY`를 설정하면 AI 정책 제안이 활성화되고, 전체 인덱스를 새로 만들 때는 아래 명령을 사용합니다.

```powershell
..\.venv\Scripts\python.exe scripts\build_rag_index.py --dry-run
..\.venv\Scripts\python.exe scripts\build_rag_index.py
```

기존 인덱스를 유지하면서 새 말뭉치만 추가할 때는 다음 명령을 사용합니다.

```powershell
..\.venv\Scripts\python.exe scripts\append_specialties_to_rag.py --input data\processed\chunks.json
..\.venv\Scripts\python.exe scripts\append_specialties_to_rag.py --input data\processed\specialty_chunks.json
..\.venv\Scripts\python.exe scripts\append_specialties_to_rag.py --input data\processed\industry_taxonomy_chunks.json
```

인덱스 갱신 후 출처 관리 대장을 재생성합니다.

```powershell
node scripts\build_source_catalog.mjs
```

생성된 `data/processed/`와 `data/rag_index/`를 제출물에 포함하면 심사 환경에서 원본 전체를 다시 처리할 필요가 없습니다. OCR 검토 대상은 `data/qa/ingestion_report.csv`에서 확인합니다.

검수에 통과한 OCR PDF는 원본을 덮어쓰지 않고 `data/ocr_output/overrides.json`에 원본 파일명과 OCR 결과 경로를 등록합니다. 말뭉치 생성 시 등록된 OCR 결과가 우선 사용됩니다.

검색은 키워드 후보 20개와 Small 벡터 후보 20개를 순위 융합한 뒤, Luna가 최종 6개 근거를 재정렬합니다. API 오류가 발생하면 자동으로 로컬 순위 결과를 사용합니다.

슬라이드·연구보고서 혼합 자료의 처리 기준은 [`docs/INGESTION_WORKFLOW.md`](docs/INGESTION_WORKFLOW.md), 출처별 기준 파일과 갱신 순서는 [`docs/RAG_SOURCE_MANAGEMENT.md`](docs/RAG_SOURCE_MANAGEMENT.md)에 정리되어 있습니다.

## Docker 실행

```powershell
Copy-Item .env.example .env
# .env에 API 키 입력
docker compose up --build
```

브라우저에서 `http://localhost:8501`로 접속합니다.

현재 작업 폴더에서는 상위 폴더의 `ABP_CONTEST_DATA.csv`와 `regional_indices_rank_final_v2_20260913.xlsx`를 자동으로 찾습니다. 배포할 때는 두 파일을 `data/raw/`에 두세요. 원본 및 파생 데이터는 Git에 포함되지 않도록 설정했습니다.

## 구조

```text
becurious/
├─ app.py                 # Streamlit 화면 및 사용자 흐름
├─ src/
│  ├─ data.py             # 데이터 검증·전처리·캐시
│  ├─ dashboard_components.py # 공통 필터·지표·상권 카드 UI
│  ├─ maps.py             # 전국/시군구 지도
│  ├─ charts.py           # 추이·업종·고객군 차트
│  ├─ analytics.py        # 지역·업종 진단 및 유사상권 계산
│  ├─ rag.py              # 정책·특산품·업종분류 통합 검색
│  ├─ agent.py            # 역할별 정책 제안 생성
│  ├─ policy_ui.py        # RAG 챗봇 및 정책 제안 대화상자
│  ├─ problem_regions.py  # 문제지역 handoff 및 회귀 기대범위 연결
│  └─ industry_taxonomy.py # 업종 코드·별칭 정규화
├─ data/
│  ├─ geo/                # 앱에 포함된 행정구역 경계
│  ├─ pdfs/               # 정책·사례 원본 PDF
│  ├─ processed/          # 문서 목록·검색 조각·사례 카드
│  ├─ qa/                 # PDF 및 수집 품질 점검 결과
│  ├─ rag_index/          # 제출 시 포함할 사전 생성 검색 인덱스
│  └─ raw/                # 원본/추가 CSV (Git 제외)
├─ output/                # 크롤링 PDF 등 중간 산출물 (Git 제외)
├─ outputs/               # 검수·공유용 최종 산출물
├─ handoff/problem_regions/ # 문제지역 판정·회귀 기대값 전달 데이터
├─ scripts/               # 수집·말뭉치·인덱스 생성 및 점검 명령
├─ config/                # 업종분류 등 검색 기본 설정
├─ docs/                  # 운영·출처·제출 문서
├─ src/ingestion/         # PDF 프로파일링·추출·청킹·검수
├─ tests/                 # 전처리 및 검색 회귀 테스트
├─ .env.example
├─ Dockerfile
├─ compose.yaml
├─ .streamlit/config.toml # 테마와 앱 설정
└─ requirements.txt
```

같은 컬럼 레이아웃의 월별 CSV로 백엔드 파일을 교체할 수 있습니다. 장기적으로 데이터가 커지면 `src/data.py`의 입력 계층을 Parquet 또는 DB 쿼리로 교체하고 화면 코드는 그대로 유지할 수 있습니다.

## 주요 기능

- 기간·업종·성별·연령 통합 필터
- 전국 시도 매출 지도와 지도 클릭 선택
- 선택 시도의 시군구 줌인 지도 및 지역 순위
- 매출액·이용건수 월별 추이
- 업종 TOP 10, 연령·성별 구성
- 상권 규모·거래활력·소비 프리미엄·업종다양성 지도
- 규모–프리미엄 사분면과 지역 유형
- 2026년 6월 주민등록인구 보정 소비강도
- 지역·업종별 전국 및 광역 순위

## 지도 데이터

행정구역 GeoJSON은 [`swcho/korea-maps`](https://github.com/swcho/korea-maps)의 통계청 SGIS 기반 경계를 WGS84 웹용으로 단순화한 자료입니다. 변환 과정은 `scripts/build_geo.py`에 보존되어 있습니다. 최근 행정구역 개편으로 일부 시군구 경계/명칭이 현재와 다를 수 있습니다.
