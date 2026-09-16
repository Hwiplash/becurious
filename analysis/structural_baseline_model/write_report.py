"""Generate Korean report and figures directly from computed result tables."""
import sys
sys.dont_write_bytecode=True
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from preprocess import OUT,TAB,CORE,NAMES,save
BLOCK={1:'인구',2:'인구·세대구조',3:'사업체·종사자',4:'산업구성',5:'모바일',6:'점포 공급',7:'주소지 구매력',8:'면적·도시 형태',9:'시도 공통효과',10:'원천징수지 임금'}
UNIT_URL='https://www.scribd.com/document/1029705754/2025%EB%85%84-%EA%B5%AD%EC%84%B8%ED%86%B5%EA%B3%84-%ED%95%B4%EC%84%A4%EC%84%9C-3%EB%B6%84%EA%B8%B0-%EA%B3%B5%EA%B0%9C-%EB%B0%98%EC%98%81'
def md(d):
    d=d.copy()
    for c in d:
        d[c]=d[c].map(lambda x:'—' if pd.isna(x) else f'{x:,.2f}' if isinstance(x,(float,np.floating)) else str(x))
    return '| '+' | '.join(d.columns)+' |\n| '+' | '.join(['---']*len(d.columns))+' |\n'+'\n'.join('| '+' | '.join(str(x).replace('|','/') for x in row)+' |' for row in d.itertuples(index=False,name=None))
def finish(fig,name):
    fig.tight_layout();fig.savefig(OUT/'figures'/name,dpi=170,bbox_inches='tight');plt.close(fig)
def generate(s,con,o,final,candidates):
    (OUT/'figures').mkdir(exist_ok=True);plt.rcParams['font.family']='Malgun Gothic';plt.rcParams['axes.unicode_minus']=False
    main=s[(s.scenario=='main')&(s.family=='log_ridge_smear')]
    a=main[(main.scope=='core9')&(main.target=='amt')].set_index('model');all11=main[(main.scope=='all11_observed')&(main.target=='amt')].set_index('model')
    progress=a.loc[['M'+str(i) for i in range(1,10)]].reset_index();progress['WAPE%']=100*progress.wape;progress['MAE(억원)']=progress.mae/1e8;progress['원단위 R²%']=100*progress.r2_original;progress['편향%']=100*progress.bias;progress['반복 SD(pp)']=progress.wape_sd*100
    fig,ax=plt.subplots(figsize=(10,5))
    for scope,label in [('core9','핵심9 관측 합계'),('all11_observed','관측11 합계')]:
        g=main[(main.scope==scope)&(main.target=='amt')].set_index('model').loc[['M'+str(i) for i in range(1,10)]];ax.errorbar(range(1,10),g.wape*100,yerr=g.wape_sd*100,marker='o',capsize=3,label=label)
    ax.set_xticks(range(1,10),['M'+str(i) for i in range(1,10)]);ax.set_ylabel('금액 WAPE (%) · 낮을수록 좋음');ax.set_title('동일 지역 OOF 5-fold × 10회 | 막대는 반복 표준편차');ax.legend();finish(fig,'01_model_block_progress.png')
    industry=main[(main.scope.isin(CORE))&(main.target=='amt')].pivot(index='industry',columns='model',values='wape').sort_values('M9');fig,ax=plt.subplots(figsize=(10,6));y=np.arange(len(industry));ax.barh(y-.18,industry.M5*100,.36,label='M5');ax.barh(y+.18,industry.M9*100,.36,label='M9');ax.set_yticks(y,industry.index);ax.set_xlabel('금액 WAPE (%)');ax.legend();ax.set_title('핵심 9업종 · 업종별 6개월 관측 지역');finish(fig,'02_industry_performance.png')
    f=final[final.scope=='core9'];fig,ax=plt.subplots(figsize=(7,6));ax.scatter(f.expected_amt/1e8,f.actual_amt/1e8,s=19,alpha=.75);lim=max(f.expected_amt.max(),f.actual_amt.max())/1e8;ax.plot([0,lim],[0,lim],'k--',lw=1);ax.set_xlabel('OOF 기대금액 (억원)');ax.set_ylabel('실제 관측금액 (억원)');ax.set_title('M9 핵심9 합계 · 점선은 관측=기대');finish(fig,'03_actual_vs_expected.png')
    h=final[final.scope.isin(CORE)];fig,ax=plt.subplots(figsize=(8,6));sc=ax.scatter(h.log_residual_cnt,h.coherent_ticket_log_residual,c=np.clip(h.log_residual_amt,-1,1),cmap='coolwarm',s=10,alpha=.6);ax.axhline(0,color='gray',lw=.7);ax.axvline(0,color='gray',lw=.7);ax.set_xlabel('거래건수 log(실제/기대)');ax.set_ylabel('정합 건당금액 log(실제/기대)');fig.colorbar(sc,ax=ax,label='금액 로그 격차');ax.set_title('두 축의 합 = 금액 로그 격차 · 핵심9');finish(fig,'04_count_ticket_residuals.png')
    regions=f.assign(abs_error=f.error_amt.abs()).nlargest(20,'abs_error').region
    heat=h[h.region.isin(regions)].pivot(index='region',columns='industry',values='log_residual_amt').reindex(regions)
    fig,ax=plt.subplots(figsize=(11,8));im=ax.imshow(heat,vmin=-.7,vmax=.7,cmap='coolwarm',aspect='auto');ax.set_xticks(range(len(heat.columns)),heat.columns,rotation=35,ha='right');ax.set_yticks(range(len(heat)),heat.index);fig.colorbar(im,ax=ax,label='log(관측/기대)',extend='both');ax.set_title('합계 절대금액 격차 상위20 · 미관측은 빈칸 · 색범위 ±0.7');finish(fig,'05_residual_structure.png')
    cs=con[(con.scope=='core9')&(con.target=='amt')&con.block.between(6,10)].copy();cs['블록']=cs.block.map(BLOCK)
    ct=cs.pivot(index='블록',columns='comparison',values='wape_gain_pp').reset_index().rename(columns={'sequential':'순차 WAPE 감소(pp)','leave_one_block_out':'제외검증 WAPE 기여(pp)'})
    # Per-industry amount/count/ticket block gains are reported side by side.
    paths=con[(con.scope.isin(NAMES))&(con.comparison=='leave_one_block_out')&con.block.isin([5,6,7,8,9])].pivot(index=['scope','industry','block'],columns='target',values='wape_gain_pp').reset_index();save(paths,'industry_count_ticket_block_pathways.csv')
    ip=con[(con.scope.isin(CORE))&(con.comparison=='leave_one_block_out')&(con.target=='amt')&con.block.isin([6,7,8,9])].pivot(index='industry',columns='block',values='wape_gain_pp').rename(columns=BLOCK).reset_index()
    de=[]
    for target,label in [('amt','이용금액'),('cnt','거래건수'),('ticket','건당금액')]:
        z=main[(main.scope=='core9')&(main.target==target)].set_index('model');de.append({'종속변수':label,'M5 WAPE%':z.loc['M5','wape']*100,'M9 WAPE%':z.loc['M9','wape']*100,'감소(pp)':(z.loc['M5','wape']-z.loc['M9','wape'])*100})
    pdpath=paths[paths.scope.isin(CORE)&paths.block.isin([5,6,7])].copy();pdpath['블록']=pdpath.block.map(BLOCK)
    coverage=pd.read_csv(TAB/'industry_coverage_main.csv',dtype={'scope':str});quality=pd.read_csv(TAB/'source_audit.csv');ext=pd.read_csv(TAB/'external_region_features.csv');loc=pd.read_csv(TAB/'localdata_store_selection.csv')
    st=pd.read_csv(TAB/'region_residual_structure.csv');stable=h[h.stable_gap]
    types=stable.residual_type.value_counts();common_n=int(st.region_common_pattern.sum());best=cs[cs.comparison=='leave_one_block_out'].sort_values('wape_gain_pp',ascending=False).iloc[0]
    sens=s[(s.scope=='core9')&(s.target=='amt')&(s.family=='log_ridge_smear')&((s.scenario.ne('main'))|s.model.isin(['M9','M9_workplace','M9_alpha10','M9_broad_supply','M9_taxable_pay','M9_mall_area','M9_current_stores']))][['scenario','model','n','wape','wape_min','wape_max','bias']].copy()
    for c in ['wape','wape_min','wape_max','bias']:sens[c]*=100
    cand=candidates.head(15)[['region','industry','ratio_amt','direction_stability','dominant_component','residual_type','error_amt']].copy();cand.error_amt/=1e8;cand=cand.rename(columns={'error_amt':'실제-기대(억원)'})
    effects=[]
    for block in [6,7,8,9]:
        z=con[(con.scope.isin(CORE))&(con.target=='amt')&(con.comparison=='leave_one_block_out')&(con.block==block)].sort_values('wape_gain_pp',ascending=False)
        effects.append(f"{BLOCK[block]} 블록은 핵심9 중 {int(z.wape_gain_pp.gt(0).sum())}업종에서 WAPE를 개선했다. 가장 높은 기여는 {z.iloc[0].industry} {z.iloc[0].wape_gain_pp:.2f}pp, 가장 낮은 기여는 {z.iloc[-1].industry} {z.iloc[-1].wape_gain_pp:.2f}pp다.")
    pathtext=[]
    for block in [5,6,7]:
        z=paths[paths.scope.isin(CORE)&paths.block.eq(block)]
        pathtext.append(f"{BLOCK[block]}: 거래건수 개선 {int(z.cnt.gt(0).sum())}/9업종, 독립 건당금액 개선 {int(z.ticket.gt(0).sum())}/9업종. 각 업종별로 개선 부호가 다를 수 있어 단일 경로로 일반화하지 않는다.")
    calibration=pd.read_csv(TAB/'calibration_by_population_and_sido.csv',dtype={'scope':str})
    cal=calibration[(calibration.scope=='core9')&(calibration.model=='M9')&(calibration.target=='amt')].copy();cal['WAPE%']=cal.wape*100;cal['편향%']=cal.bias*100
    cp=cal[cal.group_type=='population_group'][['group','n','WAPE%','편향%']]
    worst=cal[cal.group_type=='SIDO_NM'].assign(abs_bias=lambda x:x.bias.abs()).nlargest(5,'abs_bias')[['group','n','WAPE%','편향%']]
    explore=main[(main.scope.isin(['8002','8003']))&(main.target=='amt')&main.model.isin(['M5','M9'])][['industry','model','n','wape','wape_min','wape_max','bias']].copy()
    for col in ['wape','wape_min','wape_max','bias']:explore[col]*=100
    income_con=cs[(cs.comparison=='leave_one_block_out')&cs.block.eq(7)].wape_gain_pp.iloc[0]
    search=candidates[candidates.scope.isin(['8001','8004','8005','8006','8021','8301'])&candidates.residual_type.eq('업종 특이형')&candidates.dominant_component.eq('거래건수')].head(8)[['region','industry','ratio_amt','ratio_cnt','direction_stability']]
    mall=main[(main.scope=='4004')&(main.target=='amt')].set_index('model')
    mismatch=final[final.scope=='4004'].supply_count_narrow.eq(0).sum()
    report=f'''# BC 관측-기대 격차를 위한 구조적 기본모형

## 1. 새 변수를 넣으면 실제금액 오차가 얼마나 줄어드는가?

주 분석은 국내 개인(성별 1·2, 연령 1~6), 2026년 1~6월, 화성 신설4구 제외 251지역이다. **핵심9 관측 합계의 WAPE는 M5 {a.loc['M5','wape']*100:.2f}% → M9 {a.loc['M9','wape']*100:.2f}%**, {100*(a.loc['M5','wape']-a.loc['M9','wape']):.2f}pp 감소했다. 절대오차 합계의 상대 감소율은 {100*(1-a.loc['M9','wape']/a.loc['M5','wape']):.2f}%, 지역당 MAE 변화는 {(a.loc['M5','mae']-a.loc['M9','mae'])/1e8:.2f}억원이다. 관측11 합계는 {all11.loc['M5','wape']*100:.2f}% → {all11.loc['M9','wape']*100:.2f}%다.

{md(progress[['model','WAPE%','MAE(억원)','원단위 R²%','편향%','반복 SD(pp)']])}

성능은 각 반복의 전체 OOF 점수를 평균했다. 잔차·산점도는 10회 OOF 기대금액 평균에 기초하므로 그 값으로 다시 계산한 WAPE와 표의 평균 WAPE는 다르다. 반복 SD·최소~최대는 표본추출 신뢰구간이나 유의성 검정이 아니다. 편향은 Σ(예측−실제)/Σ실제로 양수는 과대예측이다.

![모형 단계](figures/01_model_block_progress.png)

core9와 all11_observed 모두 **그 범위에서 관측된 금액만 합산**한다. 모든 지역에서 9업종이 전부 관측되었다는 뜻이 아니다. 미관측 0 대체는 하지 않았다. 개별 업종은 6개월 모두 관측된 지역만 사용하며 부분관측 제외 수를 커버리지 표에 남겼다. 합계는 실제 관측행에서 직접 계산하므로, 완전관측 지역만 남긴 개별업종 분석표의 합과 항상 같지는 않다.

## 2. 어떤 블록의 설명력이 컸는가?

{md(ct)}

최종모형에서 블록을 하나씩 제외했을 때 핵심9 금액 WAPE에 가장 큰 새 블록은 **{best['블록']} ({best.wape_gain_pp:.2f}pp)**였다. 양수는 해당 블록을 넣었을 때 개선, 음수는 악화다. 순차 증가분과 제외검증은 서로 다른 조건부 비교이며, 기여를 합쳐 총소비 비중이나 인과효과로 해석할 수 없다. 원천징수지 평균임금은 M9 이후 별도 보조 블록이다.

주소지 구매력의 최종모형 제외검증 기여는 {income_con:.2f}pp다. {'음수이므로 기존 구조정보와 중복되는 구매력 블록이 합계 금액 예측을 추가로 개선했다고 주장할 수 없다.' if income_con<0 else '이는 다른 모든 블록을 조건으로 한 추가 예측 개선이며 소득의 인과효과는 아니다.'} 모든 구조변수를 포함한 사전 지정 M9를 기본모형으로 유지했고, 성능이 더 좋아 보이는 제외모형을 같은 OOF 결과로 골라 바꾸지 않았다.

M1 총인구, M2 연령5비율·여성·1/2인세대 비율, M3 사업체/종사자 규모, M4 도소매/숙박음식 사업체 비중 및 도소매/숙박음식/제조/전문과학기술 종사자 비중, M5 모바일 유입·유출이라는 기존 정의를 유지했다. 로그 모형의 M3는 인구대비 사업체/종사자, M5는 유입/인구와 유입/유출의 로그다. M1~M5의 raw Ridge와 로그 Ridge를 기존 결과와 수치 대조한다(`prior_M1_M5_reproduction.csv`).

기존 로그 피처는 **각 월 비율을 계산→6개월 평균→로그** 순서를 그대로 보존한다. 상반기 평균분자/평균분모로 바꾸지 않는다. 일반구 합산은 기존에 없던 별도 민감도이므로 합산한 반기 규모의 비율로 다시 계산한다.

M6는 업종별 점포/인구1만명의 log1p다. 합계 모형에는 해당9/11업종 공급 지표를 각각 넣어 공급 구성을 보존한다. M7은 주소지 평균급여 로그·신고인원/인구·상위시 공통값 플래그다. 일반구의 신고인원과 총액 및 신고인원/인구는 결측으로 두어 중복 배정하지 않는다. M8은 로그 인구밀도, 대·공장용지·농지임야 비중, 도시지역 면적/인구 비율, 주거·상업·공업 구성, 일반구 공통 플래그 및 행정구역 유형이다. 점포수·인구대비·면적대비를 동시에 넣지 않았다. 인구·사업체·종사자·전체/업종점포 밀도는 전처리표에 모두 보존한다.

M9는 SIDO_NM 지시변수다. 모든 계수에 같은 Ridge 벌점을 적용하므로 엄밀히는 **정규화한 시도 고정효과**다. 시도 효과는 BC 점유율·문화·가맹점 구성·누락변수 등을 흡수하며 원인별로 식별되지 않는다. 세종처럼 한 지역인 시도는 검증 fold에서 그 시도의 계수를 학습할 수 없으므로 미관측 범주로 예측한다. 전처리·결측 중앙값·표준화·범주 생성·smearing은 학습 fold에서만 계산한다. α=1을 사전 고정했으며 OOF에서 최적 모형을 선택하지 않았다. α=10을 별도 민감도로 평가했다. LOBO는 지정한 피처 블록을 제외하는 검증으로, 인구를 분모로 갖는 다른 블록까지 제거하는 인과적 변수 제거가 아니다.

## 3. 업종별 공급·구매력·밀도 효과

아래는 최종모형 제외검증의 금액 WAPE 기여(pp)다. 개별 계수의 부호나 인과적 수요탄력성이 아니다.

{md(ip)}

{' '.join(effects)}

**대형할인점은 중요한 예외다.** M5→M9 금액 WAPE가 {mall.loc['M5','wape']*100:.2f}%→{mall.loc['M9','wape']*100:.2f}%로 악화했고 M9의 평균 과대예측은 {mall.loc['M9','bias']*100:.2f}%다. α=10에서는 WAPE {mall.loc['M9_alpha10','wape']*100:.2f}%로 달라져 정규화에도 민감하다. BC가6개월 관측된193지역 중 좁은 공급 정의의 점포수가0인 지역이 {mismatch}개다. 따라서 이 업종의 큰 격차는 미설명 소비보다 공급분류·BC포착·모형부적합을 우선 점검해야 한다. 공급의 넓은 정의와 면적 추가만으로 이 문제를 해결했다고 볼 수 없다. 후보표에 모형 calibration 주의 플래그를 남겼다.

![업종 성능](figures/02_industry_performance.png)

{md(coverage[coverage.scope.isin(NAMES)][['industry','regions_any','regions_complete6','partial_regions_excluded','coverage_status']])}

한정식 16지역·갈비전문점 82지역은 별도 탐색 결과다. 소수 표본, 관측 선택 편향, 상호명 대리지표의 불완전성 때문에 핵심업종 순위에 포함하지 않았다. 전 업종 결과는 `industry_model_performance.csv`에 보존했다. 특히 대형할인점도 미관측 지역이 적지 않아 관측조건부 성능이다.

탐색 업종의 금액 성능(비율 열은 %):

{md(explore)}

## 4. 거래건수와 건당금액 중 어느 경로가 더 설명되는가?

{md(pd.DataFrame(de))}

업종별 경로는 다음의 최종모형 제외검증으로 비교한다. 단위는 각 종속변수의 WAPE 감소(pp)라서 건수와 객단가의 원단위 MAE를 직접 비교하지 않는다.

{md(pdpath[['industry','블록','amt','cnt','ticket']].rename(columns={'amt':'금액','cnt':'건수','ticket':'건당금액'}))}

{' '.join(pathtext)}

금액·건수·객단가를 독립적으로 적합했다. 독립 예측 객단가×예측건수는 일반적으로 예측금액과 다르다. 잔차의 정확한 항등분해에는 정합 기대객단가=기대금액/기대건수를 사용해 log금액격차=log건수격차+log정합객단가격차를 만든다. 이 정합 객단가는 독립 객단가모형과 다른 지표다. `direct_ticket_identity_gap`에 두 방식의 불일치를 보존했다. 핵심9 지역×업종에서 |건수 로그격차|가 |정합객단가 로그격차| 이상인 비율은 {h.dominant_component.eq('거래건수').mean()*100:.1f}%다. 이는 오차의 회계적 분해이며 실제 소비자 수나 가격의 인과적 기여가 아니다.

![건수와 객단가](figures/04_count_ticket_residuals.png)

## 5. 시도 공통효과 이후에도 지역 잔차가 남는가?

핵심9 합계 M9의 원단위 R²는 {a.loc['M9','r2_original']*100:.2f}%, 금액 WAPE 반복 범위는 {a.loc['M9','wape_min']*100:.2f}~{a.loc['M9','wape_max']*100:.2f}%다. 합계251지역 중 |log(실제/기대)|≥log(1.2)이면서 10회 중9회 이상 방향이 같은 지역은 {int(f.stable_gap.sum())}개다. 이 기준은 사전 진단 규칙이며 통계적 유의성을 의미하지 않는다. 낮은 쪽 임계값은 1/1.2≈0.833, 높은 쪽은 1.2로 로그 대칭이다.

![실제와 기대](figures/03_actual_vs_expected.png)

표·그림의 값은 **BC 관측-기대 격차**다. 실제 지역 소비, BC 카드 사용 비중, 가맹점 포착, 누락변수, 자료집계·모형오차가 섞여 있다. 점선 위를 BC 이용강도가 높다거나 사업성이 좋다고 단정하지 않는다. 인구규모별·시도별 M5/M8/M9 calibration은 `calibration_by_population_and_sido.csv`에 모든 업종·종속변수에 대해 저장했다.

반복평균 예측의 인구규모별 calibration:

{md(cp)}

시도별 절대편향이 큰5개 그룹(지역수가 작으면 해석에 특히 주의):

{md(worst)}

## 6. 지역 공통형과 업종 특이형

지역 공통형은 관측 핵심업종이6개 이상이고, 업종 로그격차 중앙값의 절대값≥log(1.2), 같은 방향 업종≥75%인 경우다. 업종 특이형은 공통형 이외에서 업종 로그격차−지역 중앙값의 절대값≥log(1.2)인 경우다. 따라서 이 분류는 통계적 잠재요인 추정이 아닌 해석용 진단이다.

지역 공통형은 251지역 중 {common_n}개다. 안정적인 핵심9 지역×업종 격차 {len(stable)}건의 구성은 {', '.join(f'{k} {v}건' for k,v in types.items())}이다. 업종별 절대금액오차 합에서 한 업종이50% 이상 차지하는 지역은 {int(st.few_industries_dominate.sum())}개다. 이 비중은 직접 적합한 합계모형의 잔차 기여율이 아니라 개별업종 모형 오차 집중도다. 업종 공통 방향과 특정 대형업종의 금액 지배를 구분해야 한다.

합계모형과 업종모형이 독립 적합되므로 잔차의 단순합도 항상 같지는 않다. `region_residual_structure.csv`에는 **합계잔차=개별업종잔차합+부분관측업종금액+(개별업종기대합−합계모형기대)**의 정합 분해를 함께 보존한다. 부분관측과 모형 간 합계 차이를 특정 업종의 기여로 오인하지 않는다.

![잔차 구조](figures/05_residual_structure.png)

## 7. 추가 외부데이터 실험 가치가 있는 곳

아래는 핵심9 중 반복 방향≥90%, 격차크기 기준을 통과하고, 공급의 넓은 정의·α=10·원천징수지 추가·상위시 그룹CV에서도 방향이 유지되는 {len(candidates)}건 중 절대금액격차 상위15건이다. 유의확률·다중검정으로 확정한 이상지역이 아니며 사업대상 추천도 아니다.

{md(cand)}

지역 공통형은 BC 가맹점 포착과 공통 누락요인을 먼저 확인한다. 업종 특이형이면서 건수 중심인 후보에서는 점포 누락을 확인한 뒤, 해당 업종의 검색 관심도가 **거래건수 OOF 오차를 줄이는지** 실험할 가치가 있다. 건당금액 중심은 상품·가격·점포구성이 우선이며 검색량과의 연결 근거는 약하다. 후보별 실험 문구는 `residual_candidates.csv`에 있다. 이번 분석에는 검색량·관광·축제 자료를 결합하지 않았고 그 데이터의 추가 설명력도 검증하지 않았다.

음식업 중 업종 특이형·건수 중심·대안모형 방향안정 조건을 만족한 검색량 실험 후보 예시는 다음과 같다. 종속변수는 거래건수다. 잔차가 존재한다는 사실만으로 검색량이 설명할 것이라고 결론 내리지 않는다.

{md(search)}

## 8. 민감도와 현재 주장할 수 없는 것

{md(sens)}

화성 통합은252지역, 일반구 상위시 합산은 화성을 제외한 별도 단위다. 일반구 합산은 인구·금액·건수·사업체·종사자·면적·점포수를 합산하고 비율을 재계산했다. 모바일은 구간 이동을 합산하므로 내부 구간 이동을 제거할 수 없다는 한계가 있다. 같은 일반구 자료를 유지하되 상위시 전체를 한 fold로 묶는 `parent_group_cv`도 수행했다. main과 민감도는 각 시나리오 안에서 동일 fold를 사용하며, 서로 다른 지역단위의 WAPE는 동일 표본 성능으로 취급하지 않는다.

원단위 raw Ridge는 비교용으로만 보존했다. 그 음수 예측을 0으로 바꾸거나 잔차 후보에 섞지 않았다. 현재 자료는 2024소득/도시계획, 2025지적면적, 2026년3월 상가단면과 2026상반기 소비를 결합한다. 동시기 설명 비교이며 실시간 예측·미래예측 검증이 아니다. 사업체 조사 기준연도와 모바일 주차값의 일평균 여부는 기존 자료에서 확정되지 않았다.

주민 구매력은 근로소득 신고자 평균의 대리변수이며 자영업·재산소득·미신고자·가구재산을 포함하는 전체 가처분소득이 아니다. 일반구 평균급여·도시형태는 상위시 공통값이므로 구간 차이의 정밀한 설명으로 해석하지 않는다. 도시 고시면적은 물/해역 등을 포함할 수 있고, 도시인구2024/주민인구2026의 분모연도도 달라 비율이1을 넘을 수 있다. 자의적으로1로 자르지 않았다.

상가 업종 분류와 BC 업종은 공식 일대일 대응이 아니며, 특히 한정식·갈비는 상호명 대리지표다. 대형점포 자료는 실제 일별 영업·BC 가맹 여부를 증명하지 못한다. 현재 모형으로 BC 시장점유율, 전체 카드시장 매출, 진짜 과소/과대소비, 관광·검색의 인과효과, 사업성과를 주장할 수 없다. 잔차는 추가 검증의 출발점이다.

실행: `python -X utf8 analysis/structural_baseline_model/run_analysis.py --rebuild`. 재검증: `python -X utf8 analysis/structural_baseline_model/validate_outputs.py`. 원본 보존 결과는 `tables/protected_file_hashes.csv`, 독립 검증은 `tables/validation_checks.csv`, 모든 파일 해시는 `artifact_manifest.csv`다.
'''
    (OUT/'report.md').write_text(report,encoding='utf-8')
    q=f'''# 데이터 품질과 전처리 기준

모든 생성 파일은 이 분석 폴더 안에 저장한다. 기존 분석 폴더 전체·외부 raw 전체·BC 원본·외부 README의 SHA-256을 작업 전후 비교한다. 기존 처리 인구·사업체·모바일 수치는 기존 지역단면 산출물을 읽고 BC 금액·건수는 원본에서 다시 집계한다. 기존 M1~M5 결과 재현 여부도 별도 검증한다.

## 업종·기간·관측

성별1/2 × 연령1~6, 202601~202606. 업종 미관측을 0으로 바꾸지 않는다. 지역×개별업종의6개월 완전관측만 비교하되 합계는 해당 범위의 관측행 합이다. 공급자료에서 완전한 지역 파일 내 분류 해당 점포가 없는 경우의 점포수0과 BC 미관측은 서로 다른 개념이다. 한정식·갈비는 탐색으로 표시한다.

## 점포 공급

2026년3월 소진공 전체 {int(quality.loc[quality.source=='store_deduplication','rows'].iloc[0]):,}개 고유점포를 스캔했다. 코드+시군구명 조합이 하나의 BC 지역에 대응하는지 확인하며 같은 시도 내 일반구 전체명/공백제거 이름의 유일성을 검증한다. 화성 신설구는 통합 민감도에서만 시로 합친다.

`store_category_crosswalk.csv`는 실제 대/중/소분류 코드·이름과 실제 표준산업분류 코드·이름의 조합별 전국 점포수, 좁은/넓은 BC 대응을 포함한다. 빈 대응은 제외다. 좁은 정의는 분류일치, 넓은 정의는 상권 소분류 우선이다. 편의점 G20405/G47122, 슈퍼마켓 G20404/G47121, 중식 I20201/02와 I56121, 서양 I204와 I56123, 제과 I21001/I56191, 분식 I21007/I56194, 일식회집 I20111·I20301와 I56114·I56122를 기준으로 한다. 일반한식은 좁게 I20101/02/99, 넓게 횟집을 제외한 I201을 쓴다. 넓은 일식에는 나머지 I203, 서양에는 피자·버거, 스넥에는 샌드위치·빙수·기타 간이를 추가한다.

한정식은 I20101에서 상호에 ‘한정식’, 갈비는 횟집을 제외한 I201에서 ‘갈비’ 포함·‘닭갈비’ 제외라는 대리규칙이다. 좁은 정의는 각각 I56111/I56113도 일치해야 한다. 우선순위 한정식→갈비→일반한식으로 최종 단일업종만 부여한다. 이 규칙은 상호에서 드러나지 않는 업태를 구분하지 못하며 공식 BC 분류가 아니다.

LOCALDATA는 인허가일≤2026-06-30, 정상영업 또는 상반기 이후 폐업/취소·휴업시작 기록이 있는 경우 중 상반기 중 영업 가능한 기록을 선별한다. 상반기 전 폐업/취소, 영업개시전, 상반기 전체 휴업은 제외한다. 휴폐업 날짜가 불명확한 비정상 상태는 제외한다. 이는 영업가능성 필터이며 실제 영업기간 확인은 아니다. 현재 정상영업만 쓴 대안도 평가한다. 인허가일은 개업일과 다를 수 있고 최신 상태에는 이후 변화가 섞인다.

좁은 정의는 업태=대형마트·준대규모점포 제외. 넓은 정의는 대형마트/구분없음/그 밖의 대규모점포 중 준대규모점포도 포함한다. 시장·쇼핑센터·백화점·복합쇼핑몰·전문점은 제외하고, 이름에 시장/상가/아울렛/백화점/쇼핑센터가 나타나는 유형 충돌도 제외한다. 분류 오류를 완전히 제거했다는 뜻은 아니다. 점포 키는 지역+도로/건물번호+정규화 상호이며 중복 인허가를 제거한다. 주소가 부족하면 관리번호를 유지하여 자동 동명이점 병합을 피한다.

같은 지역·도로/건물번호의 LOCALDATA 선택 점포가 있으면 해당 정의의 소진공 식품종합소매 점포를 제외해 공급 블록의 업종 간 중복을 방지한다. 이는 보수적인 장소 기준으로 건물 내 독립 편의점 등을 함께 제외할 수 있다. 제외 목록은 `cross_source_retail_site_exclusions.csv`에 남긴다. 합계모형은 점포수를 단순합하지 않고 업종별 공급벡터를 사용한다.

BC 거래는 관측되지만 좁은 점포수가0인 대형할인점 지역이 {mismatch}개다. 이0은 해당 공급자료와 정의에서의 부재이며 실제 모든 점포가 없다는 뜻이 아니다. `bc_observed_supply_coverage.csv`에서 업종별 불일치를 확인할 수 있다. 대형할인점 잔차는 모형부적합과 포착범위 확인을 우선한다.

인천의 분석기간 이후 주소명은3월 인천 상가정보의 도로/건물번호·법정동 대응으로 BC 지역을 복구한다. ‘전남광주통합특별시’는 BC의 광주/전남 중 시군구명이 유일하게 맞는 지역으로 대응한다. 주소 불완전은 같은 개방자치단체코드의 유일한 BC 지역이 검증될 때만 보완한다. 이 규칙과 결과를 geography_crosswalk에 보존한다. 남은 미매칭은 조용히 타 지역에 배정하지 않는다.

{md(quality[quality.source.str.startswith('LOCALDATA')][['source','selected','unmatched_rows','area_missing_rate']])}

지역별 면적합은 유효한 양수면적만 합산하고 전부 결측이면 NaN을 유지한다. 선택점포가 없으면 공급면적0이다. 면적 결측률을 별도 저장하고 M9_mall_area에서 면적과 결측률의 추가 활용 가능성을 평가한다. 소재지면적은 실제 BC 매출 발생 매장면적과 같다고 보장되지 않는다.

## 구매력 단위와 지리

제공 XLSX에는 단위 행이 없으므로 **국세청 작성 『2025년 국세통계 해설서』 p.77의4-2-14(원천징수지),4-2-15(주소지) 표 정의 ‘명, 백만 원’과 대조**했다. 열은 B급여총계 인원, C급여총계 금액, D과세대상 총급여 인원, E과세대상 총급여 금액이다. [국세청 해설서의 공개 사본]({UNIT_URL})을 확인했으며 TASIS 공식 페이지는 동적 화면이라 본문 추출이 되지 않았다. 사본 확인과 공식 사이트 직접 확인을 구분한다.

금액×1,000,000으로 원 환산. 평균급여=C/B, 과세대상1인당=E/D다. 전국 C=964,796,387백만원, B=21,078,535명 → 급여총계 평균 약45,771,511원이다. 과세대상금액943,257,648백만원은 급여총계와 다른 열이다. 임의로 두 열을 혼용하지 않는다. 주소지/원천징수지 전국행과 단위는 `income_unit_audit.csv`에 보존했다.

미추홀구(남구)는 미추홀구로 명시 교정했다. 세종은 시도행 자체가 기초단위인 예외다. 일반구 {int(ext.residence_parent_shared.sum())}개에는 상위시1인당 평균만 적용하고, 총액·신고인원·신고인원/인구는 결측을 유지한다. 일반구 공통값 플래그를 포함하고 학습 fold 내 중앙값으로 결측 처리한다. 상위시 합산 민감도에서는 원래 시의 신고인원/인구를 계산한다. 신고인원/주민인구는2024/2026의 서로 다른 시점이며 취업률과 동일하지 않다.

## 면적과 도시 형태

국토이용현황2025 계-면적(㎡)÷1e6을 km²로 쓴다. 세종 ‘합계’와 ‘세종특별자치시’ 중복행은 모든 값의 동일성을 확인해 한 번만 사용한다. 일반구와 상위시(계)는 이중합산하지 않는다. 대 비중은 건축물 부지 지목이며 상업용만 뜻하지 않는다. 농지임야=전+답+과수원+임야. 상업지역 정보는 도시계획 상업지역에서 별도 구성한다.

도시지역 총면적은 두 자료의2024 값으로 교차대조했다. 구성표의 주거/상업/공업/녹지는 면적 원자료가 아니라 1인당㎡다. 각 값×도시지역 인구÷도시지역 면적으로 구성비를 복원했다. 소수자리 반올림과 미세 구역차이로 합이1과 정확히 같지 않을 수 있다. 상위시 도시면적/상위시 총지적면적, 도시인구2024/상위시 주민인구2026을 공통 적용하며 일반구 차이로 해석하지 않는다. 도시 고시면적과 지적면적의 범위가 달라 1 초과를 자동오류로 고치지 않는다. 인구비율0 지역의 1인당 구성 복원이 불가능하면 NaN으로 남겨 학습 fold 안에서 처리한다.

## 검증·재현

범주형은 학습 fold에서만 생성하고 미관측 시도는0벡터로 처리한다. 주모형은 log(y) Ridge α=1과 학습잔차 평균 exp의 Duan 보정이며 모든 기대값은 양수다. 기본 정의는 OOF 결과로 선택하지 않았다. 최종 M9의 잔차만 후보를 만든다. 반복 방향90%·로그20%·공통방향75% 등은 진단 규칙이며 유의성 기준이 아니다. 일반구 합산과 parent_group_cv 결과로 공통값 공유 의존성을 평가한다.
'''
    (OUT/'data_quality.md').write_text(q,encoding='utf-8')
    (OUT/'README.md').write_text('''# 구조적 기본모형

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
''',encoding='utf-8')
if __name__=='__main__':
    s=pd.read_csv(TAB/'model_performance.csv',dtype={'scope':str});con=pd.read_csv(TAB/'model_block_contribution.csv',dtype={'scope':str});o=pd.read_csv(TAB/'oof_predictions.csv',dtype={'scope':str});f=pd.read_csv(TAB/'residual_diagnostics.csv',dtype={'scope':str});c=pd.read_csv(TAB/'residual_candidates.csv',dtype={'scope':str});generate(s,con,o,f,c)
