from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd


@dataclass
class RegionDiagnosis:
    region: str
    industry: str
    start_month: str
    end_month: str
    sales_change: float
    transaction_change: float
    ticket_change: float
    regional_sales_change: float
    weak_age_groups: list[str]
    growing_age_groups: list[str]
    pain_points: list[str]
    advantages: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def _change(series: pd.Series) -> float:
    series = series.sort_index()
    if len(series) < 2 or not series.iloc[0]:
        return 0.0
    return float(series.iloc[-1] / series.iloc[0] - 1)


def diagnose_region(data: pd.DataFrame, sido: str, ccg: str, industry: str) -> RegionDiagnosis:
    region = data[(data["SIDO_NM"] == sido) & (data["CCG_NM"] == ccg)]
    target = region[region["TP_BUZ_NM"] == industry]
    if target.empty:
        raise ValueError("선택한 지역과 업종에 해당하는 데이터가 없습니다.")

    monthly = target.groupby("month")[["amt", "cnt"]].sum().sort_index()
    sales_change = _change(monthly["amt"])
    transaction_change = _change(monthly["cnt"])
    ticket = monthly["amt"].div(monthly["cnt"].replace(0, pd.NA)).fillna(0)
    ticket_change = _change(ticket)

    regional_monthly = region.groupby("month")["amt"].sum().sort_index()
    regional_sales_change = _change(regional_monthly)

    age_changes: dict[str, float] = {}
    for age, frame in target.groupby("age"):
        age_changes[str(age)] = _change(frame.groupby("month")["amt"].sum())
    ordered = sorted(age_changes.items(), key=lambda item: item[1])
    weak = [age for age, value in ordered if value <= -0.05][:3]
    growing = [age for age, value in reversed(ordered) if value >= 0.05][:3]

    pains: list[str] = []
    advantages: list[str] = []
    if sales_change <= -0.05:
        pains.append(f"선택 기간 업종 매출이 {sales_change:+.1%} 감소했습니다.")
    if transaction_change <= -0.05:
        pains.append(f"거래 건수가 {transaction_change:+.1%} 감소해 고객 유입 약화 가능성이 있습니다.")
    if ticket_change <= -0.05:
        pains.append(f"건당 결제액이 {ticket_change:+.1%} 감소해 메뉴 구성·가격 전략 점검이 필요합니다.")
    if sales_change < regional_sales_change - 0.05:
        pains.append(f"지역 전체 매출 변화({regional_sales_change:+.1%})보다 해당 업종 회복력이 낮습니다.")
    if weak:
        pains.append(f"매출 감소가 큰 고객군은 {', '.join(weak)}입니다.")

    if sales_change >= 0.05:
        advantages.append(f"업종 매출이 {sales_change:+.1%} 성장하고 있습니다.")
    if ticket_change >= 0.05:
        advantages.append(f"건당 결제액이 {ticket_change:+.1%} 증가해 소비 프리미엄이 형성되고 있습니다.")
    if sales_change > regional_sales_change + 0.05:
        advantages.append("지역 전체보다 해당 업종의 성장성이 높습니다.")
    if growing:
        advantages.append(f"성장 고객군은 {', '.join(growing)}입니다.")

    if not pains:
        pains.append("뚜렷한 급락 신호는 없으며 세부 고객군별 편차를 추가 확인해야 합니다.")
    if not advantages:
        advantages.append("현재 데이터에서 뚜렷한 성장 신호가 없어 인접 상권·유사 업종 비교가 필요합니다.")

    return RegionDiagnosis(
        region=f"{sido} {ccg}",
        industry=industry,
        start_month=monthly.index.min().strftime("%Y-%m"),
        end_month=monthly.index.max().strftime("%Y-%m"),
        sales_change=sales_change,
        transaction_change=transaction_change,
        ticket_change=ticket_change,
        regional_sales_change=regional_sales_change,
        weak_age_groups=weak,
        growing_age_groups=growing,
        pain_points=pains,
        advantages=advantages,
    )

