"""Independent output, source integrity, geography and OOF validation."""
import sys,json
sys.dont_write_bytecode=True
import numpy as np
import pandas as pd
from preprocess import ROOT,OUT,TAB,OLD,CORE,NAMES,save,parent
from inspect_sources import digest,protected
CHECK=[]
def check(name,ok,detail=''):
    CHECK.append({'check':name,'passed':bool(ok),'detail':str(detail)})
    if not ok:
        save(CHECK,'validation_checks.csv');raise AssertionError(name+': '+str(detail))
def main():
    CHECK.clear()
    before=json.loads((TAB/'protected_hashes_before.json').read_text(encoding='utf-8'))
    after={str(p.relative_to(ROOT)):digest(p) for p in protected()}
    check('protected_file_set_unchanged',set(before)==set(after),len(before))
    audit=[{'path':p,'sha256_before':h,'sha256_after':after.get(p),'unchanged':h==after.get(p)} for p,h in before.items()]
    save(audit,'protected_file_hashes.csv');check('all_protected_hashes_unchanged',all(v['unchanged'] for v in audit),len(audit))
    data=pd.read_csv(TAB/'analysis_input_main.csv',dtype={'scope':str})
    b=pd.read_csv(TAB/'external_region_features.csv');check('external_region_unique_252',len(b)==252 and b.region.nunique()==252)
    check('main_region_251_no_hwaseong',data.region.nunique()==251 and not data.region.str.contains('화성시').any())
    check('land_income_urban_matched',b[['area_km2','residence_mean_pay','workplace_mean_pay','urban_area_ratio']].notna().all().all())
    check('positive_area_income',b[['area_km2','residence_mean_pay','workplace_mean_pay']].gt(0).all().all())
    units=pd.read_csv(TAB/'income_unit_audit.csv');check('income_official_units_national_totals',len(units)==2 and units.won_multiplier.eq(1000000).all() and units.filers.eq(21078535).all() and units.pay_million.eq(964796387).all())
    for mode in ['residence','workplace']:
        shared=b[mode+'_parent_shared'].eq(1)
        check(mode+'_no_duplicated_parent_totals',b.loc[shared,[mode+'_filers',mode+'_pay_total_won',mode+'_filer_population_ratio']].isna().all().all())
        check(mode+'_parent_means_constant',b[shared].groupby('parent_region')[mode+'_mean_pay'].nunique().max()==1)
    urb=pd.read_csv(TAB/'urban_area_reconciliation.csv');check('urban_source_area_reconciles',np.allclose(urb.composition_area,urb.area_table_2024,equal_nan=True),len(urb))
    cov=pd.read_csv(TAB/'industry_coverage_main.csv',dtype={'scope':str}).set_index('scope')
    check('low_observation_separated',cov.loc['8003','regions_complete6']==16 and cov.loc['8002','regions_complete6']==82)
    raw=pd.read_csv(ROOT/'data/ABP_CONTEST_DATA.csv',dtype={'GENDER_CD':str,'AGE_CD':str,'TP_BUZ_NO':str})
    raw=raw[raw.GENDER_CD.isin(['1','2'])&raw.AGE_CD.isin(list('123456'))&~raw.CCG_NM.str.startswith('화성시')&raw.STRD_YYMM.between(202601,202606)].copy();raw['region']=raw.SIDO_NM+' / '+raw.CCG_NM
    for scope,g in data.groupby('scope'):
        codes=CORE if scope=='core9' else list(NAMES) if scope=='all11_observed' else [scope]
        rr=raw[raw.TP_BUZ_NO.isin(codes)];months=rr.groupby('region').STRD_YYMM.nunique();expected=rr[rr.region.isin(months[months==6].index)].groupby('region')[['amt','cnt']].sum().sort_index();actual=g.set_index('region').sort_index()
        check('BC_amount_count_'+scope,np.allclose(expected[['amt','cnt']],actual[['amt','cnt']],rtol=1e-12))
        check('BC_missing_not_zero_'+scope,set(actual.index)==set(expected.index) and actual.amt.gt(0).all())
    perf=pd.read_csv(TAB/'model_performance_by_repeat.csv',dtype={'scope':str})
    old=pd.read_csv(OLD/'model_performance_by_repeat.csv',dtype={'scope':str});prior=old[(old.scenario=='main')&old.scope.ne('common6')].copy();prior['scope']=prior.scope.replace({'all11':'all11_observed'});prior['model']='M'+prior.stage.astype(str)
    m=perf.merge(prior,on=['scenario','scope','model','family','target','repeat'],suffixes=('_new','_old'))
    save(m[['scope','model','family','target','repeat','wape_new','wape_old','mae_new','mae_old','r2_original_new','r2_original_old']],'prior_M1_M5_reproduction.csv')
    check('reproduce_all_prior_M1_M5_metrics',len(m)==12*5*2*3*10 and np.allclose(m.wape_new,m.wape_old,atol=1e-9,rtol=1e-8),f'{len(m)} comparisons; max WAPE difference={abs(m.wape_new-m.wape_old).max()}')
    folds=pd.read_csv(TAB/'region_fold_assignments.csv');oldf=pd.read_csv(OLD/'region_fold_assignments.csv')
    for sc in ['main','hwaseong_aggregate']:
        ff=folds[folds.scenario==sc].merge(oldf[oldf.scenario==sc],on=['scenario','region','repeat']);check(sc+'_old_folds_preserved',ff.fold_x.eq(ff.fold_y).all())
    f=folds[folds.scenario=='parent_group_cv'].copy();f['parent']=f.region.map(parent);check('parent_group_cv_whole_city',f.groupby(['repeat','parent']).fold.nunique().eq(1).all())
    oo=pd.read_csv(TAB/'oof_predictions_by_repeat.csv.gz',dtype={'scope':str});check('oof_unique',not oo.duplicated(['scenario','scope','model','family','repeat','region']).any())
    check('exactly_ten_oof_repeats',oo.groupby(['scenario','scope','model','family','region']).repeat.nunique().eq(10).all())
    check('log_expectations_positive_finite',np.isfinite(oo[oo.family=='log_ridge_smear'][['expected_amt','expected_cnt','expected_ticket']]).all().all() and oo[oo.family=='log_ridge_smear'][['expected_amt','expected_cnt','expected_ticket']].gt(0).all().all())
    joined=oo.merge(folds[['scenario','repeat','region','fold']],on=['scenario','repeat','region'],suffixes=('_oof','_assigned'),validate='many_to_one');check('all_models_use_identical_folds',joined.fold_oof.eq(joined.fold_assigned).all())
    mp=perf.set_index(['scenario','scope','model','family','repeat','target']);maxdiff=0
    for key,g in oo.groupby(['scenario','scope','model','family','repeat']):
        for t in ['amt','cnt','ticket']:
            w=np.abs(g['actual_'+t]-g['expected_'+t]).sum()/g['actual_'+t].sum();maxdiff=max(maxdiff,abs(w-mp.loc[key+(t,),'wape']))
    check('all_WAPE_recomputed_from_saved_OOF',maxdiff<1e-9,maxdiff)
    from sklearn.pipeline import make_pipeline
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import Ridge
    from run_analysis import columns
    for scope in ['core9','4004','8003']:
        c=data[data.scope==scope].sort_values('region').reset_index(drop=True);f=c.region.map(folds[(folds.scenario=='main')&(folds.repeat==0)].set_index('region').fold);tr=f!=0;te=f==0
        cols=sum(columns(scope).values(),[])[:-1]  # remove optional workplace block (only last feature)
        xx=c[cols].to_numpy(float);xx=np.where(np.isfinite(xx),xx,np.nan)
        for cc in ['admin_type','SIDO_NM']:
            xx=np.column_stack([xx]+[c[cc].eq(level).to_numpy(float) for level in sorted(c.loc[tr,cc].unique())])
        pipe=make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True),StandardScaler(),Ridge(alpha=1))
        ly=np.log(c[['amt','cnt','ticket']].to_numpy());pipe.fit(xx[tr],ly[tr]);sm=np.exp(ly[tr]-pipe.predict(xx[tr])).mean(0);pred=np.exp(pipe.predict(xx[te]))*sm
        expected=oo[(oo.scenario=='main')&(oo.scope==scope)&(oo.model=='M9')&(oo.family=='log_ridge_smear')&(oo.repeat==0)&(oo.fold==0)].set_index('region').loc[c.loc[te,'region'],['expected_amt','expected_cnt','expected_ticket']]
        check('independent_sklearn_OOF_training_smear_'+scope,np.allclose(pred,expected,rtol=1e-7),float(np.max(np.abs(pred/expected.to_numpy()-1))))
    rd=pd.read_csv(TAB/'residual_diagnostics.csv');check('residual_only_main_final_log',rd.model.eq('M9').all() and rd.family.eq('log_ridge_smear').all() and rd.scenario.eq('main').all())
    check('coherent_count_ticket_identity',rd.identity_error.abs().max()<1e-10,rd.identity_error.abs().max())
    structure=pd.read_csv(TAB/'region_residual_structure.csv')
    if 'aggregate_identity_error' in structure:
        check('aggregate_industry_partial_model_identity',structure.aggregate_identity_error.abs().max()<.1,structure.aggregate_identity_error.abs().max())
    candidates=pd.read_csv(TAB/'residual_candidates.csv',dtype={'scope':str});check('candidate_rules_core_and_robust',candidates.scope.isin(CORE).all() and candidates.direction_stability.ge(.9).all() and candidates[['broad_same_direction','alpha10_same_direction','workplace_same_direction','parent_cv_same_direction']].all().all())
    for scope in ['core9','all11_observed']:
        g=pd.read_csv(TAB/'analysis_input_general_gu_aggregate.csv',dtype={'scope':str});g=g[g.scope==scope]
        check('general_gu_aggregation_preserves_'+scope,np.allclose(g[['amt','cnt']].sum(),data[data.scope==scope][['amt','cnt']].sum(),rtol=1e-12))
    loc=pd.read_csv(TAB/'localdata_store_selection.csv');check('no_market_shoppingcenter_in_discount',not loc.loc[loc.broad_selected,'업태구분명'].isin(['시장','쇼핑센터','백화점','복합쇼핑몰','전문점']).any())
    check('unique_selected_physical_store',not loc[loc.broad_selected].physical_key.duplicated().any())
    check('selected_malls_all_geographically_matched',loc.loc[loc.broad_selected,'region'].notna().all())
    required=['README.md','report.md','data_quality.md','preprocess.py','run_analysis.py','validate_outputs.py']
    check('required_documents_exist',all((OUT/p).exists() for p in required));check('five_required_figures',len(list((OUT/'figures').glob('0[1-5]_*.png')))==5)
    tables=['source_audit.csv','geography_crosswalk.csv','store_category_crosswalk.csv','model_performance.csv','model_block_contribution.csv','industry_model_performance.csv','count_ticket_decomposition.csv','oof_predictions.csv','residual_diagnostics.csv','residual_candidates.csv']
    check('all_required_tables_exist',all((TAB/p).exists() for p in tables))
    save(CHECK,'validation_checks.csv')
    manifest=[]
    for p in sorted(OUT.rglob('*')):
        if p.is_file() and p.name!='artifact_manifest.csv' and '__pycache__' not in p.parts:
            manifest.append({'path':str(p.relative_to(OUT)),'bytes':p.stat().st_size,'sha256':digest(p)})
    pd.DataFrame(manifest).to_csv(OUT/'artifact_manifest.csv',index=False,encoding='utf-8-sig')
    print('VALIDATION PASSED',len(CHECK),'checks;',len(before),'protected files;',len(manifest),'artifacts',flush=True)
if __name__=='__main__':main()
