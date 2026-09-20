# 농사로 지역특산물 수집기

농사로 `지역특산물` 목록의 모든 카드를 순회하고, 카드가 연결하는 지자체·외부 페이지에서 **해당 특산물 설명만 분리**해 항목별 PDF와 텍스트로 보존합니다. 연결 페이지 전체를 인쇄하지 않으므로 같은 페이지에 있는 다른 특산물은 PDF에 섞이지 않습니다. 카드마다 다음 정보를 `specialties.csv`에 기록합니다.

- 지역, 특산물명, 원본 URL과 최종 이동 URL
- PDF 및 추출 텍스트 경로
- 특산물명·특징 관련 문맥
- 요리·음식·레시피 관련 문맥(페이지에 있을 때만)
- 추출 신뢰도와 실패 사유

같은 외부 URL이 여러 특산물에 연결되더라도 특산물마다 별도의 PDF를 만듭니다. 외부 페이지 형식이 제각각이므로 자동 추출 결과는 `extraction_confidence=low` 행부터 검수하는 방식이 안전합니다.

## 실행

프로젝트 루트(`becurious`)에서 먼저 소량으로 확인합니다.

```powershell
..\.venv\Scripts\python.exe scripts\crawl_nongsaro_specialties.py --start-page 8 --end-page 8 --max-items 3
```

전체 192페이지 수집은 다음과 같습니다.

```powershell
..\.venv\Scripts\python.exe scripts\crawl_nongsaro_specialties.py
```

기본 출력 위치는 `output/pdf/nongsaro_specialties`입니다. 실행을 중단했다가 같은 명령을 다시 실행하면 성공한 행은 건너뜁니다. PDF 없이 구조화 데이터만 먼저 점검하려면 `--no-pdf`를 사용합니다.

## 운영 시 주의점

- 기본 1초 간격을 유지하거나 서버 상황에 따라 `--delay 2`처럼 늘립니다.
- 외부 사이트의 robots.txt, 이용약관, 저작권 및 재배포 조건을 확인합니다.
- 로그인, CAPTCHA, 폐쇄된 링크, JavaScript 전용 페이지는 `failed` 또는 낮은 신뢰도로 남을 수 있습니다.
- `foods`는 원문에 음식 정보가 확인될 때만 채워지며, 특산물명만 보고 음식을 추측하지 않습니다.
- PDF에는 지역, 특산물명, 해당 특산물의 특징, 제공된 음식 정보, 원문 URL만 들어갑니다.
