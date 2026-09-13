# ABP 상권 인사이트 대시보드

BC카드 공모전 소비 집계 데이터를 전국 → 시도 → 시군구 단위로 탐색하는 Streamlit 대시보드입니다.

## 실행

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

현재 작업 폴더에서는 상위 폴더의 `ABP_CONTEST_DATA.csv`를 자동으로 찾습니다. 배포할 때는 CSV를 `data/raw/ABP_CONTEST_DATA.csv`에 두거나 앱 사이드바에서 업로드하세요. 원본 데이터는 Git에 포함되지 않도록 설정했습니다.

## 구조

```text
becurious/
├─ app.py                 # Streamlit 화면 및 사용자 흐름
├─ src/
│  ├─ data.py             # 데이터 검증·전처리·캐시
│  ├─ maps.py             # 전국/시군구 지도
│  └─ charts.py           # 추이·업종·고객군 차트
├─ data/
│  ├─ geo/                # 앱에 포함된 행정구역 경계
│  └─ raw/                # 원본/추가 CSV (Git 제외)
├─ .streamlit/config.toml # 테마와 앱 설정
└─ requirements.txt
```

같은 컬럼 레이아웃의 월별 CSV는 업로드만으로 교체할 수 있습니다. 장기적으로 데이터가 커지면 `src/data.py`의 입력 계층을 Parquet 또는 DB 쿼리로 교체하고 화면 코드는 그대로 유지할 수 있습니다.

## 주요 기능

- 기간·업종·성별·연령 통합 필터
- 전국 시도 매출 지도와 지도 클릭 선택
- 선택 시도의 시군구 줌인 지도 및 지역 순위
- 매출액·이용건수 월별 추이
- 업종 TOP 10, 연령·성별 구성
- 필터 결과 CSV 다운로드

## 지도 데이터

행정구역 GeoJSON은 [`swcho/korea-maps`](https://github.com/swcho/korea-maps)의 통계청 SGIS 기반 경계를 WGS84 웹용으로 단순화한 자료입니다. 변환 과정은 `scripts/build_geo.py`에 보존되어 있습니다. 최근 행정구역 개편으로 일부 시군구 경계/명칭이 현재와 다를 수 있습니다.
