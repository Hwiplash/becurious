from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd
from src.total_market import personal_rows, population_context
from src.period_change import END_MONTH, START_MONTH, jan_jun_change


@dataclass
class RegionDiagnosis:
    region: str
    industry: str
    start_month: str
    end_month: str
    sales_change: float | None
    transaction_change: float | None
    ticket_change: float | None
    regional_sales_change: float | None
    weak_age_groups: list[str]
    growing_age_groups: list[str]
    pain_points: list[str]
    advantages: list[str]
    consumption_context: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _change(series: pd.Series) -> float | None:
    return jan_jun_change(series)


def diagnose_region(data: pd.DataFrame, sido: str, ccg: str, industry: str) -> RegionDiagnosis:
    region = data[(data["SIDO_NM"] == sido) & (data["CCG_NM"] == ccg)]
    target = region[region["TP_BUZ_NM"] == industry]
    if target.empty:
        raise ValueError("선택한 지역과 업종에 해당하는 데이터가 없습니다.")

    monthly = target.groupby("month")[["amt", "cnt"]].sum().sort_index()
    sales_change = _change(monthly["amt"])
    transaction_change = _change(monthly["cnt"])
    ticket = monthly["amt"].div(monthly["cnt"].replace(0, pd.NA))
    ticket_change = _change(ticket)

    regional_monthly = region.groupby("month")["amt"].sum().sort_index()
    regional_sales_change = _change(regional_monthly)

    age_changes: dict[str, float] = {}
    for age, frame in personal_rows(target).groupby("age"):
        value = _change(frame.groupby("month")["amt"].sum())
        if value is not None:
            age_changes[str(age)] = value
    ordered = sorted(age_changes.items(), key=lambda item: item[1])
    weak = [age for age, value in ordered if value <= -0.05][:3]
    growing = [age for age, value in reversed(ordered) if value >= 0.05][:3]

    pains: list[str] = []
    advantages: list[str] = []
    if sales_change is not None and sales_change <= -0.05:
        pains.append(f"선택 기간 업종 매출이 {sales_change:+.1%} 감소했습니다.")
    if transaction_change is not None and transaction_change <= -0.05:
        pains.append(f"거래 건수가 {transaction_change:+.1%} 감소해 고객 유입 약화 가능성이 있습니다.")
    if ticket_change is not None and ticket_change <= -0.05:
        pains.append(f"건당 결제액이 {ticket_change:+.1%} 감소해 메뉴 구성·가격 전략 점검이 필요합니다.")
    if sales_change is not None and regional_sales_change is not None and sales_change < regional_sales_change - 0.05:
        pains.append(f"지역 전체 매출 변화({regional_sales_change:+.1%})보다 해당 업종 회복력이 낮습니다.")
    if weak:
        pains.append(f"매출 감소가 큰 고객군은 {', '.join(weak)}입니다.")

    if sales_change is not None and sales_change >= 0.05:
        advantages.append(f"업종 매출이 {sales_change:+.1%} 성장하고 있습니다.")
    if ticket_change is not None and ticket_change >= 0.05:
        advantages.append(f"건당 결제액이 {ticket_change:+.1%} 증가해 소비 프리미엄이 형성되고 있습니다.")
    if sales_change is not None and regional_sales_change is not None and sales_change > regional_sales_change + 0.05:
        advantages.append("지역 전체보다 해당 업종의 성장성이 높습니다.")
    if growing:
        advantages.append(f"성장 고객군은 {', '.join(growing)}입니다.")

    if not pains:
        pains.append("1월·6월 중 관측되지 않은 달이 있어 변화율을 산출하지 못했습니다." if sales_change is None
                     else "뚜렷한 급락 신호는 없으며 세부 고객군별 편차를 추가 확인해야 합니다.")
    if not advantages:
        advantages.append("1월·6월 변화율을 산출할 수 없어 성장 여부를 판단하지 않았습니다." if sales_change is None
                          else "현재 데이터에서 뚜렷한 성장 신호가 없어 인접 상권·유사 업종 비교가 필요합니다.")

    return RegionDiagnosis(
        region=f"{sido} {ccg}",
        industry=industry,
        start_month=START_MONTH.strftime("%Y-%m"),
        end_month=END_MONTH.strftime("%Y-%m"),
        sales_change=sales_change,
        transaction_change=transaction_change,
        ticket_change=ticket_change,
        regional_sales_change=regional_sales_change,
        weak_age_groups=weak,
        growing_age_groups=growing,
        pain_points=pains,
        advantages=advantages,
        consumption_context=population_context(sido, ccg, industry),
    )


def find_similar_districts(
    data: pd.DataFrame,
    indices: dict[str, pd.DataFrame],
    sido: str,
    ccg: str,
    industry: str,
    top_k: int = 5,
) -> list[dict]:
    """전국 시군구를 체력지수·업종추이·연령구조로 비교한다."""
    base = indices["지역지수"][[
        "시도", "시군구", "결제금액 규모지수", "거래활력지수", "업종다양성지수",
    ]].copy()
    premium = indices["프리미엄"][["시도", "시군구", "6개월 통합 프리미엄지수"]].copy()
    population = indices["인구보정"][[
        "시도", "시군구", "개인 금액 지수(평균=100)", "개인 건수 지수(평균=100)",
    ]].copy()
    features = base.merge(premium, on=["시도", "시군구"], how="inner").merge(
        population, on=["시도", "시군구"], how="inner"
    )

    industry_data = data[data["TP_BUZ_NM"] == industry].copy()
    if industry_data.empty:
        return []
    keys = ["SIDO_NM", "CCG_NM"]
    monthly = industry_data.groupby(keys + ["month"])[["amt", "cnt"]].sum().reset_index()
    first = monthly[monthly["month"].eq(START_MONTH)].set_index(keys)
    last = monthly[monthly["month"].eq(END_MONTH)].set_index(keys)
    endpoints = first.join(last, how="inner", lsuffix="_jan", rsuffix="_jun")
    dynamics = pd.DataFrame(index=endpoints.index)
    dynamics["업종매출변화"] = endpoints["amt_jun"].div(endpoints["amt_jan"].replace(0, np.nan)).sub(1)
    dynamics["업종거래변화"] = endpoints["cnt_jun"].div(endpoints["cnt_jan"].replace(0, np.nan)).sub(1)
    first_ticket = endpoints["amt_jan"].div(endpoints["cnt_jan"].replace(0, np.nan))
    last_ticket = endpoints["amt_jun"].div(endpoints["cnt_jun"].replace(0, np.nan))
    dynamics["업종객단가변화"] = last_ticket.div(first_ticket.replace(0, np.nan)).sub(1)
    dynamics["업종관측월수"] = monthly.groupby(keys)["month"].nunique()
    dynamics = dynamics.reset_index().rename(columns={"SIDO_NM": "시도", "CCG_NM": "시군구"})

    industry_amount = industry_data.groupby(keys)["amt"].sum()
    total_amount = data.groupby(keys)["amt"].sum()
    share = industry_amount.div(total_amount.replace(0, np.nan)).rename("업종매출비중").reset_index()
    share = share.rename(columns={"SIDO_NM": "시도", "CCG_NM": "시군구"})

    age_amount = personal_rows(industry_data).groupby(keys + ["age"])["amt"].sum()
    age_share = age_amount.div(age_amount.groupby(level=keys).transform("sum")).unstack(fill_value=0)
    age_share.columns = [f"연령비중_{column}" for column in age_share.columns]
    age_share = age_share.reset_index().rename(columns={"SIDO_NM": "시도", "CCG_NM": "시군구"})

    features = features.merge(dynamics, on=["시도", "시군구"], how="inner")
    features = features[features["업종관측월수"] >= 4].copy()
    features = features.merge(share, on=["시도", "시군구"], how="inner")
    features = features.merge(age_share, on=["시도", "시군구"], how="left")
    target_mask = (features["시도"] == sido) & (features["시군구"] == ccg)
    if not target_mask.any() or len(features) < 2:
        return []

    index_columns = [
        "결제금액 규모지수", "거래활력지수", "6개월 통합 프리미엄지수", "업종다양성지수",
        "개인 금액 지수(평균=100)", "개인 건수 지수(평균=100)",
    ]
    dynamics_columns = ["업종매출변화", "업종거래변화", "업종객단가변화", "업종매출비중"]
    age_columns = [column for column in features if column.startswith("연령비중_")]
    feature_columns = index_columns + dynamics_columns + age_columns
    numeric = features[feature_columns].apply(pd.to_numeric, errors="coerce")
    medians = numeric.median()
    numeric = numeric.fillna(medians)
    scale = numeric.quantile(.75).sub(numeric.quantile(.25)).replace(0, 1).fillna(1)
    normalized = numeric.sub(medians).div(scale).clip(-5, 5)

    weights = pd.Series(0.0, index=feature_columns)
    weights[index_columns] = 0.55 / len(index_columns)
    weights[dynamics_columns] = 0.30 / len(dynamics_columns)
    if age_columns:
        weights[age_columns] = 0.15 / len(age_columns)
    target_vector = normalized.loc[target_mask].iloc[0]
    distances = np.sqrt(normalized.sub(target_vector).pow(2).mul(weights, axis=1).sum(axis=1))
    ranked = features.loc[~target_mask, ["시도", "시군구"]].copy()
    ranked["distance"] = distances.loc[~target_mask]
    ranked = ranked.sort_values("distance").head(top_k)

    results = []
    for row_index, row in ranked.iterrows():
        values = numeric.loc[row_index]
        results.append({
            "region": f"{row['시도']} {row['시군구']}",
            "distance": round(float(row["distance"]), 4),
            "match_score": round(float(100 / (1 + row["distance"])), 1),
            "scale_index": round(float(values["결제금액 규모지수"]), 1),
            "activity_index": round(float(values["거래활력지수"]), 1),
            "premium_index": round(float(values["6개월 통합 프리미엄지수"]), 1),
            "diversity_index": round(float(values["업종다양성지수"]), 1),
            "industry_sales_change": round(float(values["업종매출변화"]), 4),
            "industry_transaction_change": round(float(values["업종거래변화"]), 4),
            "industry_ticket_change": round(float(values["업종객단가변화"]), 4),
            "industry_sales_share": round(float(values["업종매출비중"]), 4),
        })
    return results
