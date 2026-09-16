"""Reproduce M1-M5 and extend structural baseline; deterministic repeated regional OOF."""
import sys, os, json, warnings
sys.dont_write_bytecode=True
os.environ.setdefault('LOKY_MAX_CPU_COUNT','1')
import numpy as np
import pandas as pd
from sklearn.model_selection import KFold
from threadpoolctl import threadpool_limits
from preprocess import OUT,ROOT,TAB,OLD,CORE,NAMES,save,parent,main as preprocess
warnings.filterwarnings('ignore',category=pd.errors.PerformanceWarning)
STRUCT=['share_u20','share_20s','share_30s','share_40s','share_50s','female_share','hh1_share','hh2_share']
SECTOR=['est_share_G','est_share_I','emp_share_G','emp_share_I','emp_share_C','emp_share_M']
SEEDS=list(range(20260913,20260923));TARGETS=['amt','cnt','ticket']
PERF=[];OOF=[];FIT=[];FOLDS=[];FEATURES=[]
def metrics(y,p):
    e=y-p;ss=((y-y.mean())**2).sum()
    return dict(n=len(y),mae=np.abs(e).mean(),wape=np.abs(e).sum()/y.sum(),r2_original=1-(e**2).sum()/ss if ss else np.nan,bias=(p-y).sum()/y.sum(),sse=(e**2).sum(),nonpositive=int((p<=0).sum()))
def fit(x,z,y,alpha=1,log=True,unscaled_tail=0):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',RuntimeWarning);med=np.nanmedian(x,axis=0)
    med=np.where(np.isfinite(med),med,0);x=np.where(np.isfinite(x),x,med);z=np.where(np.isfinite(z),z,med)
    mu=x.mean(0);sd=x.std(0);sd=np.where(sd<1e-12,1,sd)
    x=(x-mu)/sd;z=(z-mu)/sd
    ly=np.log(y) if log else y;ym=ly.mean(0);ys=ly.std(0);ys=np.where(ys<1e-12,1,ys)
    co=np.linalg.solve(x.T@x+alpha*np.eye(x.shape[1]),x.T@((ly-ym)/ys))
    latent=z@co*ys+ym;sm=np.exp(ly-(x@co*ys+ym)).mean(0) if log else np.ones(y.shape[1])
    pred=np.exp(latent)*sm if log else latent
    return pred,sm,co,med
def load_bc():
    d=pd.read_csv(ROOT/'data/ABP_CONTEST_DATA.csv',dtype={'GENDER_CD':str,'AGE_CD':str,'TP_BUZ_NO':str})
    d=d[d.GENDER_CD.isin(['1','2'])&d.AGE_CD.isin(list('123456'))&d.STRD_YYMM.between(202601,202606)].copy()
    d['region']=d.SIDO_NM+' / '+d.CCG_NM
    return d
def collapse_features(b):
    b=b.copy();b['aggregate_region']=b.region.map(parent);rec=[]
    additive=['population','households','inflow','outflow','area_km2','all_store_count']+[c for c in b if c.startswith(('est_','emp_')) and len(c.split('_'))==2 and c.split('_')[1] in list('ABCDEFGHIJKLMNOPQRS')+['0']]+[c for c in b if c.startswith('store_') and c.split('_')[-1] in NAMES]+['mall_narrow','mall_broad','mall_strict','mall_narrow_area_m2','mall_broad_area_m2']
    for r,g in b.groupby('aggregate_region'):
        v=g.iloc[0].to_dict();v['region']=r;v['CCG_NM']=r.split(' / ')[1];v['parent_region']=r
        for c in additive:v[c]=g[c].sum(min_count=1)
        for c in STRUCT+['share_60plus']:
            w=g.households if c.startswith('hh') else g.population;v[c]=np.average(g[c],weights=w)
        for c in ['land_building_share','land_factory_share','land_farm_forest_share']:v[c]=np.average(g[c],weights=g.area_km2)
        for definition in ['narrow','broad']:
            den=g['mall_'+definition].sum()
            v['mall_'+definition+'_area_missing_rate']=(g['mall_'+definition+'_area_missing_rate']*g['mall_'+definition]).sum()/den if den else 0
        for col in ['population','est_0','emp_0','all_store_count']+[f'store_{d}_{s}' for d in ['narrow','broad'] for s in NAMES]:
            v[col+'_density']=v[col]/v['area_km2']
            if col.startswith('store_'):v[col+'_per10k']=v[col]/v['population']*10000
        v['urban_parent_shared']=0;v['admin_type']='시' if len(g)>1 else v['admin_type']
        for mode in ['residence','workplace']:
            inc=pd.read_csv(TAB/f'income_{mode}_municipality.csv').set_index('source_region')
            if r in inc.index:
                v[mode+'_filers']=inc.loc[r,'filers'];v[mode+'_pay_total_won']=inc.loc[r,'pay_total_won'];v[mode+'_filer_population_ratio']=inc.loc[r,'filers']/v['population']
            v[mode+'_parent_shared']=0
        for c in SECTOR:
            a,_,s=c.split('_');v[c]=v[a+'_'+s]/v[a+'_0']
        rec.append(v)
    return pd.DataFrame(rec).drop(columns='aggregate_region')
def build(bc,base,scenario):
    bc=bc.copy();b=base.copy()
    if scenario=='hwaseong_aggregate':bc.loc[bc.CCG_NM.str.startswith('화성시'),'region']='경기도 / 화성시'
    else:
        bc=bc[~bc.CCG_NM.str.startswith('화성시')];b=b[~b.CCG_NM.str.startswith('화성시')]
    if scenario=='general_gu_aggregate':
        bc['region']=bc.region.map(parent);b=collapse_features(b)
    scopes={'core9':CORE,'all11_observed':list(NAMES)}|{k:[k] for k in NAMES};panels=[];coverage=[]
    for scope,codes in scopes.items():
        z=bc[bc.TP_BUZ_NO.isin(codes)].groupby(['region','STRD_YYMM']).agg(amt=('amt','sum'),cnt=('cnt','sum'),observed_industries=('TP_BUZ_NO','nunique')).reset_index()
        n=z.groupby('region').STRD_YYMM.nunique();complete=n[n==6].index
        z=z[z.region.isin(complete)].groupby('region').agg(amt=('amt','sum'),cnt=('cnt','sum'),observed_industries_mean=('observed_industries','mean'),observed_industries_min=('observed_industries','min')).reset_index()
        z=z.merge(b.drop(columns='observed_industries',errors='ignore'),on='region',validate='one_to_one');z['scope']=scope;z['industry']=NAMES.get(scope,scope);z['ticket']=z.amt/z.cnt
        z['coverage_status']='exploratory' if scope in ['8002','8003'] else 'core'
        z['log_population']=np.log(z.population)
        # Prior M1-M5 took the mean of monthly ratios, then logged it.
        # Preserve those supplied fields exactly; ratio of H1 means is different.
        if scenario=='general_gu_aggregate':
            for nm,a,den in [('est_per_population','est_0','population'),('emp_per_population','emp_0','population'),('inflow_per_population','inflow','population'),('in_out_ratio','inflow','outflow')]:z['log_'+nm]=np.log(z[a]/z[den])
        z['log_population_density']=np.log(z.population/z.area_km2)
        for mode in ['residence','workplace']:
            z['log_'+mode+'_mean_pay']=np.log(z[mode+'_mean_pay']);z['log_'+mode+'_mean_tax_pay']=np.log(z[mode+'_mean_tax_pay'])
        for definition in ['narrow','broad']:
            for s in codes:z['supply_'+definition+'_'+s]=np.log1p(z['store_'+definition+'_'+s]/z.population*10000)
        z['supply_strict_4004']=np.log1p(z.mall_strict/z.population*10000)
        z['log_mall_area_per_population']=np.log1p(z.mall_narrow_area_m2/z.population)
        coverage.append({'scenario':scenario,'scope':scope,'industry':NAMES.get(scope,scope),'regions_any':len(n),'regions_complete6':len(z),'partial_regions_excluded':int(n.lt(6).sum()),'regions_total':len(b),'observed_industries_min':z.observed_industries_min.min(),'coverage_status':z.coverage_status.iloc[0]})
        panels.append(z)
    save(coverage,f'industry_coverage_{scenario}.csv');result=pd.concat(panels,ignore_index=True);save(result,f'analysis_input_{scenario}.csv')
    return result
def columns(scope,raw=False,definition='narrow'):
    codes=CORE if scope=='core9' else list(NAMES) if scope=='all11_observed' else [scope]
    return {1:['population'] if raw else ['log_population'],2:STRUCT,3:['est_0','emp_0'] if raw else ['log_est_per_population','log_emp_per_population'],4:SECTOR,5:['inflow','outflow'] if raw else ['log_inflow_per_population','log_in_out_ratio'],6:['supply_'+definition+'_'+s for s in codes],7:['log_residence_mean_pay','residence_filer_population_ratio','residence_parent_shared'],8:['log_population_density','land_building_share','land_factory_share','land_farm_forest_share','urban_area_ratio','urban_population_ratio','urban_residential_share','urban_commercial_share','urban_industrial_share','urban_parent_shared'],9:[],10:['log_workplace_mean_pay']}
def get_folds(data,scenario):
    reg=sorted(data.region.unique())
    if scenario in ['main','hwaseong_aggregate']:
        f=pd.read_csv(OLD/'region_fold_assignments.csv');f=f[f.scenario==scenario].copy()
    else:
        groups=sorted(set(map(parent,reg))) if scenario=='parent_group_cv' else reg
        rec=[]
        for repeat,seed in enumerate(SEEDS):
            for fold,(_,te) in enumerate(KFold(5,shuffle=True,random_state=seed).split(groups)):
                test={groups[i] for i in te}
                rec.extend({'scenario':scenario,'region':r,'repeat':repeat,'seed':seed,'fold':fold} for r in reg if (parent(r) if scenario=='parent_group_cv' else r) in test)
        f=pd.DataFrame(rec)
    assert len(f)==len(reg)*10 and not f.duplicated(['repeat','region']).any();FOLDS.append(f)
    return f
def evaluate(data,scenario,full=False):
    folds=get_folds(data,scenario)
    for scope,c in data.groupby('scope',sort=False):
        c=c.sort_values('region').reset_index(drop=True);y=c[TARGETS].to_numpy(float)
        print('CV',scenario,scope,len(c),flush=True)
        specs=[('M'+str(k),list(range(1,k+1)),False,'narrow',1) for k in (range(1,10) if full else [5,9])]
        if full:
            specs += [('without_M'+str(k),[s for s in range(1,10) if s!=k],False,'narrow',1) for k in range(1,10)]
            specs += [('M9_workplace',list(range(1,11)),False,'narrow',1),('M9_broad_supply',list(range(1,10)),False,'broad',1),('M9_alpha10',list(range(1,10)),False,'narrow',10),('M9_taxable_pay',list(range(1,10)),False,'narrow',1)]
            specs += [('M'+str(k),list(range(1,k+1)),True,'narrow',10) for k in [1,2,3,4,5,9]]
            if scope in ['4004','core9','all11_observed']:
                specs += [('M9_mall_area',list(range(1,10)),False,'narrow',1),('M9_current_stores',list(range(1,10)),False,'narrow',1)]
        for label,blocks,raw,definition,alpha in specs:
            family='raw_ridge' if raw else 'log_ridge_smear';bd=columns(scope,raw,definition);cols=sum([bd[k] for k in blocks],[])
            if label=='M9_taxable_pay':cols=[s.replace('log_residence_mean_pay','log_residence_mean_tax_pay') for s in cols]
            if label=='M9_mall_area':cols+=['log_mall_area_per_population','mall_narrow_area_missing_rate']
            if label=='M9_current_stores':cols=[s.replace('supply_narrow_4004','supply_strict_4004') for s in cols]
            cat=(['admin_type'] if 8 in blocks else [])+(['SIDO_NM'] if 9 in blocks else [])
            FEATURES.extend({'scope':scope,'model':label,'family':family,'feature':col,'first_block':next((k for k,v in bd.items() if col in v),8 if col=='admin_type' else 9)} for col in cols+cat) if scenario=='main' else None
            xx=c[cols].to_numpy(float)
            for repeat in range(10):
                f=c.region.map(folds[folds.repeat==repeat].set_index('region').fold).to_numpy();pred=np.full_like(y,np.nan)
                for k in range(5):
                    tr=f!=k;te=~tr
                    if not te.any():continue
                    assert not set(c.loc[tr,'region'])&set(c.loc[te,'region'])
                    if scenario=='parent_group_cv':assert not set(c.loc[tr,'parent_region'])&set(c.loc[te,'parent_region'])
                    x=xx[tr];z=xx[te];cn=[]
                    for cc in cat:
                        # Categories discovered in training only. Full indicators + ridge with intercept.
                        for level in sorted(c.loc[tr,cc].dropna().unique()):
                            x=np.column_stack([x,c.loc[tr,cc].eq(level).to_numpy(float)]);z=np.column_stack([z,c.loc[te,cc].eq(level).to_numpy(float)]);cn.append(cc+'='+level)
                    pp,sm,co,med=fit(x,z,y[tr],alpha,not raw);pred[te]=pp
                    FIT.append({'scenario':scenario,'scope':scope,'model':label,'family':family,'repeat':repeat,'fold':k,'train_n':int(tr.sum()),'validation_n':int(te.sum()),'features':x.shape[1],'alpha':alpha,'smear_amt':sm[0],'smear_cnt':sm[1],'smear_ticket':sm[2],'disjoint_regions':True,'train_region_hash':__import__('hashlib').sha256('|'.join(c.loc[tr,'region']).encode()).hexdigest(),'training_only_preprocessing':True})
                assert np.isfinite(pred).all(),(scenario,scope,label)
                if not raw:assert (pred>0).all()
                for j,t in enumerate(TARGETS):PERF.append({'scenario':scenario,'scope':scope,'industry':c.industry.iloc[0],'model':label,'family':family,'target':t,'repeat':repeat,'alpha':alpha,**metrics(y[:,j],pred[:,j])})
                o=c[['region','SIDO_NM','CCG_NM','parent_region','population','scope','industry','coverage_status']].copy();o['scenario']=scenario;o['model']=label;o['family']=family;o['repeat']=repeat;o['fold']=f
                for j,t in enumerate(TARGETS):o['actual_'+t]=y[:,j];o['expected_'+t]=pred[:,j]
                OOF.append(o)
def summarize():
    p=pd.DataFrame(PERF);save(p,'model_performance_by_repeat.csv')
    keys=['scenario','scope','industry','model','family','target']
    s=p.groupby(keys).agg(n=('n','first'),wape=('wape','mean'),wape_sd=('wape','std'),wape_min=('wape','min'),wape_max=('wape','max'),mae=('mae','mean'),r2_original=('r2_original','mean'),bias=('bias','mean'),sse=('sse','mean'),nonpositive=('nonpositive','mean')).reset_index()
    save(s,'model_performance.csv');save(s[s.scope.isin(NAMES)],'industry_model_performance.csv')
    contrib=[]
    for key,g in p[(p.scenario=='main')&(p.family=='log_ridge_smear')].groupby(['scope','industry','target','repeat']):
        g=g.set_index('model')
        for k in range(2,11):
            a='M'+str(k-1);b='M'+str(k) if k<10 else 'M9_workplace'
            if k==10:a='M9'
            contrib.append(dict(zip(['scope','industry','target','repeat'],key))|{'comparison':'sequential','block':k,'wape_gain_pp':100*(g.loc[a,'wape']-g.loc[b,'wape']),'sse_reduction':1-g.loc[b,'sse']/g.loc[a,'sse']})
        for k in range(1,10):
            a='without_M'+str(k);contrib.append(dict(zip(['scope','industry','target','repeat'],key))|{'comparison':'leave_one_block_out','block':k,'wape_gain_pp':100*(g.loc[a,'wape']-g.loc['M9','wape']),'sse_reduction':1-g.loc['M9','sse']/g.loc[a,'sse']})
    con=pd.DataFrame(contrib);save(con,'model_block_contribution_by_repeat.csv')
    cs=con.groupby(['scope','industry','target','comparison','block']).agg(wape_gain_pp=('wape_gain_pp','mean'),gain_sd=('wape_gain_pp','std'),gain_min=('wape_gain_pp','min'),gain_max=('wape_gain_pp','max'),sse_reduction=('sse_reduction','mean')).reset_index();save(cs,'model_block_contribution.csv')
    oo=pd.concat(OOF,ignore_index=True);save(oo,'oof_predictions_by_repeat.csv.gz')
    keys=['scenario','scope','industry','model','family','region','SIDO_NM','CCG_NM','parent_region','coverage_status']
    o=oo.groupby(keys)[['population']+['actual_'+t for t in TARGETS]+['expected_'+t for t in TARGETS]].mean().reset_index()
    for t in TARGETS:
        o['error_'+t]=o['actual_'+t]-o['expected_'+t];o['ratio_'+t]=o['actual_'+t]/o['expected_'+t].where(o['expected_'+t]>0);o['log_residual_'+t]=np.log(o['ratio_'+t])
    save(o,'oof_predictions.csv');save(FIT,'training_fold_audit.csv');save(pd.concat(FOLDS),'region_fold_assignments.csv');save(pd.DataFrame(FEATURES).drop_duplicates(),'model_feature_dictionary.csv')
    return s,cs,o,oo
def diagnostics(s,con,o,oo):
    final=o[(o.scenario=='main')&(o.model=='M9')&(o.family=='log_ridge_smear')].copy()
    reliability=s[(s.scenario=='main')&(s.model=='M9')&(s.family=='log_ridge_smear')&(s.target=='amt')][['scope','wape','bias']].rename(columns={'wape':'industry_amount_wape','bias':'industry_amount_bias'})
    final=final.merge(reliability,on='scope',validate='many_to_one');final['model_calibration_caution']=final.industry_amount_wape.gt(.5)|final.industry_amount_bias.abs().gt(.1)
    inp=pd.read_csv(TAB/'analysis_input_main.csv',dtype={'scope':str});supply=[]
    for scope,g in inp[inp.scope.isin(NAMES)].groupby('scope'):
        supply.extend({'scope':scope,'region':v.region,'supply_count_narrow':v['store_narrow_'+scope],'supply_count_broad':v['store_broad_'+scope]} for _,v in g.iterrows())
    supply=pd.DataFrame(supply);save(supply,'bc_observed_supply_coverage.csv');final=final.merge(supply,on=['scope','region'],how='left',validate='one_to_one');final['supply_zero_with_bc_observed']=final.supply_count_narrow.eq(0)
    final['coherent_expected_ticket']=final.expected_amt/final.expected_cnt
    final['coherent_ticket_log_residual']=np.log(final.actual_ticket/final.coherent_expected_ticket)
    final['identity_error']=final.log_residual_amt-final.log_residual_cnt-final.coherent_ticket_log_residual
    final['direct_ticket_identity_gap']=final.log_residual_amt-final.log_residual_cnt-final.log_residual_ticket
    final['dominant_component']=np.where(final.log_residual_cnt.abs()>=final.coherent_ticket_log_residual.abs(),'거래건수','건당금액')
    rep=oo[(oo.scenario=='main')&(oo.model=='M9')&(oo.family=='log_ridge_smear')].copy();rep['positive']=rep.actual_amt>rep.expected_amt;rep['log_r']=np.log(rep.actual_amt/rep.expected_amt)
    stable=rep.groupby(['scope','region']).agg(positive_fraction=('positive','mean'),log_residual_min=('log_r','min'),log_residual_max=('log_r','max'),log_residual_sd=('log_r','std')).reset_index()
    final=final.merge(stable,on=['scope','region'],validate='one_to_one');final['direction_stability']=np.maximum(final.positive_fraction,1-final.positive_fraction);final['stable_gap']=final.direction_stability.ge(.9)&final.log_residual_amt.abs().ge(np.log(1.2))
    # Sensitivity stability is separate from repeat-CV stability.
    for model,alias in [('M9_broad_supply','broad'),('M9_alpha10','alpha10'),('M9_workplace','workplace')]:
        q=o[(o.scenario=='main')&(o.model==model)&(o.family=='log_ridge_smear')][['scope','region','log_residual_amt']].rename(columns={'log_residual_amt':alias+'_log_residual'})
        final=final.merge(q,on=['scope','region'],validate='one_to_one')
        final[alias+'_same_direction']=np.sign(final.log_residual_amt)==np.sign(final[alias+'_log_residual'])
    q=o[(o.scenario=='parent_group_cv')&(o.model=='M9')&(o.family=='log_ridge_smear')][['scope','region','log_residual_amt']].rename(columns={'log_residual_amt':'parent_cv_log_residual'})
    final=final.merge(q,on=['scope','region'],validate='one_to_one');final['parent_cv_same_direction']=np.sign(final.log_residual_amt)==np.sign(final.parent_cv_log_residual)
    final['robust_candidate']=final.stable_gap&final.broad_same_direction&final.alpha10_same_direction&final.workplace_same_direction&final.parent_cv_same_direction
    structural=[]
    for r,g in final[final.scope.isin(CORE)].groupby('region'):
        med=g.log_residual_amt.median();direction=np.sign(med);share=(np.sign(g.log_residual_amt)==direction).mean();a=g.error_amt.abs();top=a.max()/a.sum()
        agg=final[(final.region==r)&(final.scope=='core9')].iloc[0]
        partial=agg.actual_amt-g.actual_amt.sum();model_gap=g.expected_amt.sum()-agg.expected_amt
        structural.append({'region':r,'observed_core_industries':len(g),'common_log_residual':med,'same_direction_fraction':share,'region_common_pattern':len(g)>=6 and share>=.75 and abs(med)>=np.log(1.2),'top_industry_abs_error_share':top,'dominating_industry':g.loc[a.idxmax(),'industry'],'few_industries_dominate':top>=.5,'count_dominant_fraction':g.dominant_component.eq('거래건수').mean(),'stable_industry_gaps':g.stable_gap.sum(),'aggregate_error_amt':agg.error_amt,'sum_industry_error_amt':g.error_amt.sum(),'partial_observation_amount':partial,'independent_model_aggregation_gap':model_gap,'aggregate_identity_error':agg.error_amt-g.error_amt.sum()-partial-model_gap})
    st=pd.DataFrame(structural);final=final.merge(st,on='region',validate='many_to_one');final['industry_specific_log_residual']=final.log_residual_amt-final.common_log_residual
    final['residual_type']=np.where(final.region_common_pattern,'지역 공통형',np.where(final.industry_specific_log_residual.abs()>=np.log(1.2),'업종 특이형','혼합/작은 격차'))
    save(st,'region_residual_structure.csv');save(final,'residual_diagnostics.csv');save(final,'count_ticket_decomposition.csv')
    candidates=final[final.scope.isin(CORE)&final.robust_candidate].copy()
    candidates['priority_abs_error']=candidates.error_amt.abs();candidates['next_experiment']=np.where(candidates.region_common_pattern,'BC 포착범위·공통 누락요인 검증 우선',np.where(candidates.dominant_component.eq('거래건수'),'점포 포착범위 검증 후 검색 관심도→거래건수 OOF 개선 실험','상품·가격·점포구성 검증 우선; 검색량은 후순위'))
    candidates.loc[candidates.scope.eq('4004'),'next_experiment']='점포분류·면적·BC가맹포착·모형정규화 재검증 우선; 검색량 후순위'
    candidates['recommendation_status']='추가 검증 후보; 사업대상 추천 아님'
    candidates=candidates.sort_values('priority_abs_error',ascending=False);save(candidates,'residual_candidates.csv')
    search=candidates[candidates.scope.isin(['8001','8004','8005','8006','8021','8301'])&candidates.residual_type.eq('업종 특이형')&candidates.dominant_component.eq('거래건수')].copy();search['experiment_target']='거래건수';search['evidence_status']='추가 데이터 미결합; 설명력 향상 미검증';save(search,'search_experiment_candidates.csv')
    cal=[]
    for (scope,model),g in o[(o.scenario=='main')&(o.family=='log_ridge_smear')&(o.model.isin(['M5','M8','M9']))].groupby(['scope','model']):
        g=g.copy();g['population_group']=pd.cut(g.population,[0,50000,150000,300000,np.inf],labels=['<5만','5–15만','15–30만','30만+'])
        for typ in ['SIDO_NM','population_group']:
            for label,h in g.groupby(typ,observed=True):
                for t in TARGETS:cal.append({'scope':scope,'model':model,'group_type':typ,'group':label,'target':t,**metrics(h['actual_'+t].to_numpy(),h['expected_'+t].to_numpy())})
    save(cal,'calibration_by_population_and_sido.csv')
    return final,candidates
def main():
    if '--report-only' in sys.argv:
        s=pd.read_csv(TAB/'model_performance.csv',dtype={'scope':str});con=pd.read_csv(TAB/'model_block_contribution.csv',dtype={'scope':str});o=pd.read_csv(TAB/'oof_predictions.csv',dtype={'scope':str});oo=pd.read_csv(TAB/'oof_predictions_by_repeat.csv.gz',dtype={'scope':str})
        final,candidates=diagnostics(s,con,o,oo)
        from write_report import generate
        generate(s,con,o,final,candidates)
        from validate_outputs import main as validate
        validate();return
    if '--rebuild' in sys.argv or not (TAB/'external_region_features.csv').exists():preprocess()
    base=pd.read_csv(TAB/'external_region_features.csv');bc=load_bc();data=build(bc,base,'main');evaluate(data,'main',True)
    for scenario in ['hwaseong_aggregate','general_gu_aggregate']:
        d=build(bc,base,scenario);evaluate(d,scenario)
    evaluate(data,'parent_group_cv')
    s,con,o,oo=summarize();final,candidates=diagnostics(s,con,o,oo)
    from write_report import generate
    generate(s,con,o,final,candidates)
    import sklearn
    (OUT/'environment.json').write_text(json.dumps({'python':sys.version,'numpy':np.__version__,'pandas':pd.__version__,'sklearn':sklearn.__version__,'seeds':SEEDS,'folds':5,'log_alpha':1,'raw_alpha':10,'primary_model':'M9 log_ridge_smear narrow supply; prespecified, no OOF model selection'},ensure_ascii=False,indent=2),encoding='utf-8')
    from validate_outputs import main as validate
    validate()
if __name__=='__main__':
    with threadpool_limits(limits=1):main()
