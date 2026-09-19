# 오늘 완성·제출 체크리스트

## 현재 완료된 상태

- 173개 PDF 전수 목록화 및 중복·손상·OCR 필요 여부 점검
- 유효 문서 162개에서 검색 조각 22,741개 생성
- 정책·실행 사례 카드 2,746개 생성
- API 없이 작동하는 로컬 근거 검색 구현
- 매출 진단 + PDF 근거 + LLM 정책 제안 화면 연결
- Docker 및 로컬 실행 환경 구성

## 본인이 해야 할 일

1. `.env.example`을 `.env`로 복사한다.
2. `.env`의 `OPENAI_API_KEY`에 본인 키를 입력한다. 키는 제출 파일이나 Git에 포함하지 않는다.
3. 아래 명령으로 앱을 실행한다.

```powershell
..\.venv\Scripts\python.exe -m streamlit run app.py
```

4. AI 정책 제안 화면에서 실제 공모전 시나리오 3건을 시험한다.
   - 대전의 갈비 전문점 부진
   - 청주의 20대 고객 감소 업종
   - 지역 강점이 뚜렷한 외식업종의 관광 연계
5. 결과에서 문서명과 페이지가 실제 PDF 내용과 맞는지 표본 검수한다.

## 선택 작업: 의미 기반 검색 추가

로컬 키워드 검색만으로 시연은 가능하다. 의미가 비슷하지만 같은 단어가 없는 사례까지 찾으려면 API 키를 설정한 뒤 다음을 한 번 실행한다.

```powershell
..\.venv\Scripts\python.exe scripts\build_rag_index.py
```

대상은 전체 22,741개 조각이 아니라 선별된 2,746개 사례 카드이므로 비용과 처리 시간을 줄였다.

## 제출 폴더에 포함할 것

- 앱 소스: `app.py`, `src/`, `config/`, `.streamlit/`
- 실행 환경: `requirements.txt`, `Dockerfile`, `compose.yaml`, `.env.example`
- 정제 결과: `data/processed/`, `data/qa/`
- 의미 검색을 만들었다면 `data/rag_index/`
- 원본 PDF는 대회 용량 제한과 재배포 가능 여부를 확인한 뒤 포함 여부 결정
- 출처 파일: `outputs/source_catalog/지역외식산업_AI_출처관리대장.xlsx`

## 제출 전 금지 사항

- `.env` 또는 API 키 제출 금지
- 출처 확인 없이 LLM 생성 결과를 확정 정책처럼 표현하지 않기
- OCR 검토 대상 문서의 문장을 핵심 근거로 단독 사용하지 않기
- 매출 상관관계를 정책 효과의 인과관계로 표현하지 않기
