# 구조적 기본모형

실행(원본부터 전처리·모형·보고서·검증 재생성):

```powershell
python -X utf8 analysis/structural_baseline_model/run_analysis.py --rebuild
python -X utf8 analysis/structural_baseline_model/validate_outputs.py
```

`--rebuild` 생략 시 이 폴더의 전처리표를 재사용한다. Python·NumPy·pandas·scikit-learn·matplotlib·threadpoolctl이 필요하다. XLSX는 표준 ZIP/XML로 읽어 openpyxl이 필요 없다. 네트워크는 실행에 필요 없다. 데이터와 기존 분석 경로는 프로젝트 루트를 기준으로 찾는다. 실행시간은 CPU/디스크에 따라 수분 이상이다.

- `report.md`: 8개 분석 질문, 실제 결과와 해석 한계.
- `data_quality.md`: 업종/지역 대응, 소득 단위, 영업기간, 관측·결측 규칙.
- `preprocess.py`: 새 외부 자료 전처리. `inspect_sources.py`: ZIP/XML와 보호 해시 함수.
- `run_analysis.py`: M1~M9, 원천징수지 보조, 모든 블록 제외, 반복 지역 CV, 세 민감도 지리 시나리오.
- `write_report.py`: 계산 결과로 한국어 문서와 그림 생성.
- `validate_outputs.py`: 원본 SHA-256, 기존 M1~M5 재현, BC 집계, fold, sklearn 독립 재적합, 잔차 항등식 검증.
- `tables/model_performance.csv`: 반복 OOF 점수 평균과 변동성. WAPE·bias·R²는 비율 단위다.
- `tables/model_block_contribution.csv`: 순차/블록제외 기여. WAPE 기여는 pp, 양수가 개선이다.
- `tables/oof_predictions.csv`: 모든 모형의 반복평균 예측. `oof_predictions_by_repeat.csv.gz`: 각 반복·fold 예측.
- `tables/count_ticket_decomposition.csv`: 최종 M9 금액·건수·독립/정합 객단가 잔차.
- `tables/residual_diagnostics.csv`, `residual_candidates.csv`: 반복·대안모형 안정성과 검증 후보. 후보는 핵심9만.
- `tables/industry_count_ticket_block_pathways.csv`: 업종별 모바일·공급·소득·형태·시도 블록의 건수/객단가 기여.
- `tables/source_audit.csv`, `geography_crosswalk.csv`, `store_category_crosswalk.csv`: 출처·지역·분류 감사.
- `tables/protected_hashes_before.json`: 최초 작업 전 해시 기준점. 재실행 때 덮어쓰지 않는다.
- `tables/protected_file_hashes.csv`, `validation_checks.csv`: 실행 후 원본 보존 및 검증.
- `artifact_manifest.csv`: 이 폴더의 모든 산출물 SHA-256(자기 자신과 Python 캐시 제외).

핵심9 범위 `core9`, 관측11 범위 `all11_observed`. 두 합계 모두 관측값의 합이며 미관측0 대체 없음. 금액 원, 건수 건, 객단가 원/건. 주 분석251지역; 화성4구 제외. 일반구 합산·화성통합·상위시 그룹CV는 민감도로만 사용한다. 모델은 업종/합계별 독립 적합이며 같은 지역은 모든 업종에서 같은 검증 fold에 속한다. 주모형은 M9 로그 Ridge α=1, 좁은 공급정의로 사전 고정했다. 검색량·관광·축제는 결합하지 않는다.
