# 전체 고객코드 BC M9 handoff

기존 `../problem_regions/` 개인 JSON을 보존한다. 새 기본 모집단은 내국인 개인(1·2), 외국인(3), 법인(x)의 합계다. 외국인의 남녀 성별은 구분되지 않고 AGE_CD x는 법인 연령 미적용이다.

`total_market_problem_regions.jsonl`은 251지역, 15,060개 월별 행(6개월 × 9업종 및 핵심9 관측 합계)을 포함한다. actual과 expected는 `all_customer_codes`이며 이를 서비스상 `total_market`으로 부른다. 연령·성별 고객구조는 `domestic_personal`만을 사용한다. legacy personal은 이 집단의 분석용 별칭이다.

월별 expected는 10회 지역 OOF 평균, pi_center는 반복0의 proper_train 모형 보정중심이다. 두 값은 서로 다르며 덮어쓰지 않는다. 구간은 전체 소비로 새로 적합·보정했다. 핵심9 합계의 기대값은 직접 합계모형이고 업종 기대값을 더한 값과 같지 않다. actual 합계는 관측 업종의 합이며 미관측은 null이다.

금액·건수 단위는 원/월·건/월이다. 부분관측 업종에는 관측 실제를 유지하고 기대값·구간을 null로 제공한다. band_status와 model_warning을 화면에 반영한다. 대형할인점 모형은 오차가 커 개별 지역 판정에 주의가 필요하다.

개인 모형 최종 후보 90곳 중 67곳 유지, 23곳 탈락, 15곳 추가되어 전체 후보는 82곳이다. 낮은 소비를 상권 쇠퇴나 정책 문제로 확정하지 않는다. 전체 카드시장·지역 실제 총매출로 표현하지 않는다.

검증과 전체 결과는 프로젝트 상위 `analysis/total_market_problem_detection/report.md`를 참조한다. UI의 `src/total_market.py`가 두 모집단을 분리하여 읽으며 RAG에는 전체 상태·개인 상태·판정 차이·외국인/법인 소비와 개인 고객구조를 별도로 전달한다.
