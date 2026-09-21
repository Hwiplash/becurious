# 전체 고객코드 BC M9 handoff

기존 `../problem_regions/` 개인 JSON을 보존한다. 새 기본 모집단은 내국인 개인(1·2), 외국인(3), 법인(x)의 합계다. 외국인의 남녀 성별은 구분되지 않고 AGE_CD x는 법인 연령 미적용이다.

`total_market_problem_regions.jsonl`은 251지역, 15,060개 월별 행(6개월 × 9업종 및 핵심9 관측 합계)을 포함한다. actual과 expected는 `all_customer_codes`이며 이를 서비스상 `total_market`으로 부른다. 연령·성별 고객구조는 `domestic_personal`만을 사용한다. legacy personal은 이 집단의 분석용 별칭이다.

월별 expected는 10회 지역 OOF 평균, pi_center는 반복0의 proper_train 모형 보정중심이다. 두 값은 서로 다르며 덮어쓰지 않는다. 구간은 전체 소비로 새로 적합·보정했다. 핵심9 합계의 기대값은 직접 합계모형이고 업종 기대값을 더한 값과 같지 않다. actual 합계는 관측 업종의 합이며 미관측은 null이다.

금액·건수 단위는 원/월·건/월이다. 6개월 중 4~5개월 관측되고 1~3월과 4~6월 각각 최소 1개월이 있으며 6개월 M9 설명변수가 준비된 지역×업종에는 6개월 모두 서비스용 기대값·90% 구간을 제공한다. 관측 실제는 전체 고객 합계를 유지하고 미관측 실제는 null로 둔다. 실제선은 미관측 월을 연결하지 않는다. 대형할인점 모형은 오차가 커 개별 지역 판정에 주의가 필요하다.

부분관측은 `band_status=partial_observation_inference`, `prediction_interval_source=total_M9_split_conformal_complete6_partial_series_inference`로 식별한다. 전체 고객 M9를 동일 업종의 완전관측 지역에서 학습·보정하며 대상 지역 실측은 학습·보정에 들어가지 않는다. 기존 10회 지역 fold·전처리·월 효과·일수 환산을 유지하고, expected는 10회 지역 제외 예측 평균, pi_center와 구간은 반복 0 proper_train 및 월별 split-conformal이다. 개인 예측 복사나 비율 확대를 사용하지 않는다.

부분관측 집단의 90% 포함률은 별도 검증하지 않았다(`partial_coverage_validated=false`). `total_calibration_ok_*`는 완전관측 보정 표본의 인구규모별 진단만 뜻한다. `extrapolation_warning=true`이면 학습 범위를 벗어난 설명변수 목록과 `band_message`를 보여준다. 문제지역 후보는 계속 완전관측 자료만 사용하며 전체 고객 82지역·88신호를 유지한다.

구간을 제공하지 않는 상태는 `no_observation`(0개월), `insufficient_observation`(4개월 미만 또는 반기 조건 미충족), `missing_model_features`(M9 변수 미준비), `insufficient_calibration`(유한 구간 산출 불가)이다. 구체적 사유는 `band_exclusion_reason`에 기록한다. UI는 `prediction_interval_available`에 따라 밴드를 그리고 `band_message`를 표시한다. 대상 목록·생성 수·정의는 manifest의 `partial_observation_inference`, 검증 결과는 validation summary의 `partial_observation_fix`를 확인한다.

개인 모형 최종 후보 90곳 중 67곳 유지, 23곳 탈락, 15곳 추가되어 전체 후보는 82곳이다. 낮은 소비를 상권 쇠퇴나 정책 문제로 확정하지 않는다. 전체 카드시장·지역 실제 총매출로 표현하지 않는다.

검증과 전체 결과는 프로젝트 상위 `analysis/total_market_problem_detection/report.md`를 참조한다. UI의 `src/total_market.py`가 두 모집단을 분리하여 읽으며 RAG에는 전체 상태·개인 상태·판정 차이·외국인/법인 소비와 개인 고객구조를 별도로 전달한다.
