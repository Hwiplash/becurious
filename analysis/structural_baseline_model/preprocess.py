"""Read-only source processing. All writes stay within this analysis directory."""
from pathlib import Path
import sys, re, json, warnings
sys.dont_write_bytecode=True
import numpy as np
import pandas as pd
warnings.filterwarnings('ignore',category=pd.errors.PerformanceWarning)
from inspect_sources import rows, digest, protected
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]; RAW=ROOT/'data/external/raw'; TAB=OUT/'tables'
OLD=ROOT/'analysis/business_mobility_explanatory_power/tables'
NAMES={'4004':'대형할인점','4010':'편의점','4020':'슈퍼마켓','8001':'일반한식','8002':'갈비전문점','8003':'한정식','8004':'일식회집','8005':'중국음식','8006':'서양음식','8021':'스넥','8301':'제과점'}
CORE=[s for s in NAMES if s not in ['8002','8003']]
PROVINCES=['서울특별시','부산광역시','대구광역시','인천광역시','광주광역시','대전광역시','울산광역시','세종특별자치시','경기도','강원특별자치도','충청북도','충청남도','전북특별자치도','전라남도','경상북도','경상남도','제주특별자치도']
SHORT=['서울','부산','대구','인천','광주','대전','울산','세종','경기','강원','충북','충남','전북','전남','경북','경남','제주']
ALIASES=dict(zip(SHORT,PROVINCES))|{x:x for x in PROVINCES}|{'강원도':PROVINCES[9],'전라북도':PROVINCES[12]}
AUDIT=[]; GEO=[]
def save(d,name):
    p=TAB/name;p.parent.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(d).to_csv(p,index=False,encoding='utf-8-sig',float_format='%.15g')
def num(s):return pd.to_numeric(s.astype(str).str.replace(',','',regex=False),errors='coerce')
def normalize(s):return ALIASES.get(str(s).strip(),str(s).strip())
def key(s,n):
    s=normalize(s);n=str(n).strip()
    if s=='인천광역시' and n in ['남구','미추홀구(남구)']:n='미추홀구'
    if s=='세종특별자치시' and n in ['세종','세종시','세종특별자치시','소계','합계']:n='세종특별자치시'
    return s+' / '+n
def parent(r):
    s,n=r.split(' / ')
    return s+' / '+n.split()[0] if ' ' in n and n.endswith('구') else r
def street_key(a):
    m=re.search(r'([^\s,]+(?:로|길))\s+(\d+(?:-\d+)?)',str(a))
    return m[1]+' '+m[2] if m else ''
def region_base():
    a=pd.read_csv(OLD/'region_industry_cross_section_hwaseong_aggregate.csv',dtype={'scope':str})
    return a[a.scope=='all11'].drop(columns=['amt','cnt','ticket','industry','scope']).reset_index(drop=True)
def match(s,n,universe):
    r=key(s,n)
    if r in universe:return r
    hits=[v for v in universe if v.replace(' ','')==r.replace(' ','')]
    if len(hits)==1:return hits[0]
    hits=[v for v in universe if v.startswith(normalize(s)+' / ') and v.endswith(' '+str(n))]
    return hits[0] if len(hits)==1 else None
def land_urban(base):
    univ=set(base.region)
    d=pd.read_csv(RAW/'kosis_land_use_by_sigungu_and_general_gu_2024_2025.csv',encoding='cp949')
    d=d[d['항목']=='면적'].copy();d['region']=[match(s,n,univ) for s,n in zip(d['시도'],d['시군구'])]
    save(d[d.region.isna()], 'land_unmatched_source_rows.csv')
    GEO.extend({'source':'land','source_sido':s,'source_name':n,'bc_region':r,'method':'name_unique_or_exact'} for s,n,r in d[['시도','시군구','region']].drop_duplicates().itertuples(index=False,name=None))
    matched=d.dropna(subset=['region'])
    assert matched.groupby(['region','레벨01'])['2025 년'].nunique().max()==1
    w=matched.drop_duplicates(['region','레벨01']).pivot(index='region',columns='레벨01',values='2025 년').apply(num)
    assert len(w)==252 and not w.index.duplicated().any()
    f=pd.DataFrame(index=w.index);f['area_km2']=w['계']/1e6
    for nm,cats in [('land_building_share',['대']),('land_factory_share',['공장용지']),('land_farm_forest_share',['전','답','과수원','임야'])]:
        assert all(c in w for c in cats),(nm,w.columns)
        f[nm]=w[cats].sum(axis=1,min_count=len(cats))/w['계']
    save(w.reset_index(),'land_2025_wide.csv')
    u=pd.read_csv(RAW/'kosis_urban_area_composition_per_capita_by_municipality_2024.csv').iloc[1:].copy()
    u['source_region']=[key(s,n) for s,n in zip(u.iloc[:,0],u.iloc[:,1])]
    # Sejong subtotal is itself a municipality. Other subtotals remain excluded.
    u=u[(u.iloc[:,1]!='소계')|u.iloc[:,0].eq('세종특별자치시')].set_index('source_region')
    uu=pd.DataFrame(index=u.index);uu['urban_population']=num(u['2024']);uu['urban_area_m2']=num(u['2024.1'])
    for nm,col in [('residential','2024.3'),('commercial','2024.4'),('industrial','2024.5'),('green','2024.6')]:
        uu['urban_'+nm+'_share']=num(u[col])*uu.urban_population/uu.urban_area_m2
    # Independently check official total urban area table.
    ar=pd.read_csv(RAW/'kosis_urban_area_by_municipality_2022_2024.csv',dtype=str);sido=None;checks=[]
    for _,v in ar.iterrows():
        n=v.iloc[0]
        if n in ALIASES:sido=normalize(n)
        r=key(sido,n)
        if r in uu.index:checks.append({'region':r,'composition_area':uu.loc[r,'urban_area_m2'],'area_table_2024':pd.to_numeric(v['2024'],errors='coerce')})
    save(checks,'urban_area_reconciliation.csv')
    bf=base.set_index('region').join(f);bf['parent_region']=[parent(r) for r in bf.index]
    pa=bf.groupby('parent_region').area_km2.sum();pp=bf.groupby('parent_region').population.sum()
    for r,v in bf.iterrows():
        pr=v.parent_region
        if pr in uu.index:
            for c in uu:bf.loc[r,c]=uu.loc[pr,c]
            bf.loc[r,'urban_area_ratio']=uu.loc[pr,'urban_area_m2']/(pa[pr]*1e6)
            bf.loc[r,'urban_population_ratio']=uu.loc[pr,'urban_population']/pp[pr]
        bf.loc[r,'urban_parent_shared']=int(pr!=r)
        GEO.append({'source':'urban','source_name':pr,'bc_region':r,'method':'parent_common_intensities' if pr!=r else 'exact'})
    # Source population and area totals are not duplicated into child districts in model inputs.
    bf=bf.drop(columns=['urban_population','urban_area_m2'])
    AUDIT.append({'source':'land','rows':len(d),'matched_regions':len(f),'unit':'2025 square metres / 1e6','note':'계-면적; 대 is building land, not exclusively commercial'})
    AUDIT.append({'source':'urban','rows':len(u),'matched_regions':bf.urban_area_ratio.notna().sum(),'unit':'2024 area m2; component columns m2/person','note':'components reconstructed from rounded m2/person; population denominator 2026 midpoint, cross-year proxy; legal area may include water'})
    return bf.reset_index()
def income(base):
    units=[]
    for mode in ['residence','workplace']:
        p=RAW/f'nts_earned_income_by_{mode}_municipality_2024.xlsx';rec=[];sido=None
        for row in rows(p):
            v={re.sub(r'\d','',k):v for k,v in row.items()};n=v.get('A','')
            if n=='전국':
                units.append({'source':p.name,'table_id':'4-2-15' if mode=='residence' else '4-2-14','reference_year':2024,'filers':float(v['B'].replace(',','')),'pay_million':float(v['C'].replace(',','')),'tax_filers':float(v['D'].replace(',','')),'tax_pay_million':float(v['E'].replace(',','')),'official_unit':'명, 백만 원','won_multiplier':1000000,'unit_evidence':'국세청 2025 국세통계 해설서 p77; publicly hosted copy; TASIS dynamic page not extractable'})
            if n in SHORT:
                sido=normalize(n)
                if n!='세종':continue
                n='세종특별자치시'
            if not sido or not re.sub(r'\(.*\)','',n).endswith(('시','군','구')):continue
            vals={c:float(str(v.get(k,'')).replace(',','')) if str(v.get(k,'')).replace(',','').replace('.','').isdigit() else np.nan for c,k in [('filers','B'),('pay_million','C'),('tax_filers','D'),('tax_pay_million','E')]}
            rec.append({'source_region':key(sido,n),'original_name':n,**vals})
        d=pd.DataFrame(rec).set_index('source_region');assert not d.index.duplicated().any()
        d['pay_total_won']=d.pay_million*1e6;d['tax_pay_total_won']=d.tax_pay_million*1e6
        d['mean_pay']=d.pay_total_won/d.filers;d['mean_tax_pay']=d.tax_pay_total_won/d.tax_filers
        save(d.reset_index(),f'income_{mode}_municipality.csv')
        for i,v in base.iterrows():
            pr=v.parent_region
            if pr in d.index:
                z=d.loc[pr]
                for c in ['mean_pay','mean_tax_pay']:base.loc[i,mode+'_'+c]=z[c]
                if pr==v.region:
                    for c in ['filers','pay_total_won','tax_pay_total_won']:base.loc[i,mode+'_'+c]=z[c]
                    base.loc[i,mode+'_filer_population_ratio']=z.filers/v.population
                GEO.append({'source':mode,'source_name':z.original_name,'source_region':pr,'bc_region':v.region,'method':'parent_per_filer_only' if pr!=v.region else ('rename_인천남구_to_미추홀구' if '남구' in z.original_name and '미추홀' in pr else 'exact')})
            base.loc[i,mode+'_parent_shared']=int(pr!=v.region)
        AUDIT.append({'source':p.name,'rows':len(d),'matched_regions':base[mode+'_mean_pay'].notna().sum(),'unit':'amount million KRW; converted x1000000','note':'general-gu totals and filer/pop ratio left missing; only mean pay shared'})
    save(units,'income_unit_audit.csv')
    return base
def assign_category(d,broad=False):
    c=d['상권업종소분류코드'];k=d['표준산업분류코드'].fillna('');name=d['상호명'].fillna('')
    out=pd.Series('',index=d.index)
    mappings={'4020':['G20404'],'4010':['G20405'],'8004':['I20111','I20301'],'8005':['I20201','I20202'],'8006':['I20401','I20402','I20403','I20499'],'8021':['I21007'],'8301':['I21001']}
    if broad:
        mappings['8004']+=['I20302','I20303','I20399'];mappings['8006']+=['I21003','I21004'];mappings['8021']+=['I21005','I21008','I21099']
    for code,cat in mappings.items():out.loc[c.isin(cat)]=code
    korean=c.str.startswith('I201')&~c.eq('I20111')
    out.loc[korean if broad else c.isin(['I20101','I20102','I20199'])]='8001'
    # Explicitly labelled lexical proxies; no official one-to-one taxonomy exists.
    out.loc[korean&name.str.contains('갈비',regex=False)&~name.str.contains('닭갈비',regex=False)]='8002'
    out.loc[c.eq('I20101')&name.str.contains('한정식',regex=False)]='8003'
    if not broad:
        good={'4020':k.eq('G47121'),'4010':k.eq('G47122'),'8004':k.isin(['I56114','I56122']),'8005':k.eq('I56121'),'8006':k.eq('I56123'),'8021':k.eq('I56194'),'8301':k.eq('I56191'),'8001':k.str.startswith('I5611'),'8002':k.eq('I56113'),'8003':k.eq('I56111')}
        for bc,ok in good.items():out.loc[out.eq(bc)&~ok]=''
    return out
def stores(base):
    univ=set(base.region);allcounts=[];cross=[];geos=[];seen=set();duplicates=0
    malls=pd.read_csv(TAB/'localdata_store_selection.csv')
    locations={mode:set(zip(malls.loc[malls[mode+'_selected']&malls.street_key.notna(),'region'],malls.loc[malls[mode+'_selected']&malls.street_key.notna(),'street_key'])) for mode in ['narrow','broad']}
    overlap=[]
    cols=['상가업소번호','상호명','상권업종대분류코드','상권업종대분류명','상권업종중분류코드','상권업종중분류명','상권업종소분류코드','상권업종소분류명','표준산업분류코드','표준산업분류명','시도명','시군구코드','시군구명','도로명주소']
    for p in sorted((RAW/'소상공인시장진흥공단_상가(상권)정보_20260331').glob('*.csv')):
        print('Store supply',p.name,flush=True);nr=0;unmatched=0
        for d in pd.read_csv(p,usecols=cols,dtype=str,chunksize=100000):
            nr+=len(d);dup=d.상가업소번호.isin(seen)|d.상가업소번호.duplicated();duplicates+=int(dup.sum());d=d[~dup].copy();seen.update(d.상가업소번호)
            g=d[['시도명','시군구코드','시군구명']].drop_duplicates();g['region']=[match(s,n,univ) for s,n in zip(g.시도명,g.시군구명)]
            # Existing Hwaseong city total is used only in the explicit aggregate sensitivity.
            g.loc[g.시군구명.str.startswith('화성시'),'region']='경기도 / 화성시'
            geos.append(g);d=d.merge(g,on=['시도명','시군구코드','시군구명'],validate='many_to_one');unmatched+=int(d.region.isna().sum())
            for v in ['narrow','broad']:
                d[v]=assign_category(d,v=='broad')
                retail=d[v].isin(['4010','4020'])
                hit=retail&pd.Series([(r,street_key(a)) in locations[v] for r,a in zip(d.region,d.도로명주소)],index=d.index)
                q=d.loc[hit,['상가업소번호','상호명','도로명주소','region',v]].rename(columns={v:'excluded_bc_scope'});q['definition']=v;overlap.append(q)
                d.loc[hit,v]=''
            cross.append(d.groupby(cols[2:10]+['narrow','broad'],dropna=False).size().rename('stores').reset_index())
            for definition in ['narrow','broad']:
                q=d[d[definition]!=''].groupby(['region',definition]).size().rename('stores').reset_index().rename(columns={definition:'scope'});q['definition']=definition;allcounts.append(q)
            q=d.groupby('region').size().rename('stores').reset_index();q['scope']='all_store';q['definition']='all';allcounts.append(q)
        AUDIT.append({'source':p.name,'rows':nr,'unmatched_rows':unmatched,'unit':'unique store IDs at March 2026 snapshot','note':'snapshot, not exact H1 operating exposure'})
    cr=pd.concat(cross).groupby(cols[2:10]+['narrow','broad'],dropna=False).stores.sum().reset_index()
    cr['mapping_status']=np.where(cr.narrow.isin(['8002','8003'])|cr.broad.isin(['8002','8003']),'lexical_proxy_not_official_BC_equivalence','classification_proxy')
    save(cr,'store_category_crosswalk.csv')
    g=pd.concat(geos).drop_duplicates();g=g.rename(columns={'시군구코드':'source_code','시군구명':'source_name','region':'bc_region','시도명':'source_sido'});g['source']='store';g['method']='code_name_pair';GEO.extend(g.to_dict('records'))
    assert g.groupby('source_code').bc_region.nunique().max()==1
    counts=pd.concat(allcounts).groupby(['region','scope','definition']).stores.sum().reset_index()
    save(counts,'store_counts_by_definition.csv');save(pd.concat(overlap,ignore_index=True),'cross_source_retail_site_exclusions.csv');AUDIT.append({'source':'store_deduplication','rows':len(seen),'duplicates_removed':duplicates})
    return counts
def localdata(base):
    d=pd.read_csv(RAW/'생활_대규모점포.csv',encoding='cp949',dtype=str);n=len(d);d=d.drop_duplicates('관리번호').copy()
    univ=set(base.region)
    # Resolve post-period address names using March source streets and legal dongs.
    ip=next((RAW/'소상공인시장진흥공단_상가(상권)정보_20260331').glob('*인천*.csv'))
    inc=pd.read_csv(ip,usecols=['시군구명','법정동명','도로명주소'],dtype=str)
    dongmap={n:sorted(set(g.시군구명)) for n,g in inc.groupby('법정동명')}
    inc['street']=inc.도로명주소.map(street_key)
    streetmap={n:sorted(set(g.시군구명)) for n,g in inc[inc.street!=''].groupby('street')}
    def addr(a):
        z=str(a).split()
        if len(z)<2:return None
        s=normalize(z[0]);nn=' '.join(z[1:3]) if len(z)>2 and z[1].endswith('시') and z[2].endswith('구') else z[1]
        if s=='세종특별자치시':return key(s,'세종')
        if s=='전남광주통합특별시':
            hits=[r for r in univ if r.split(' / ')[0] in ['광주광역시','전라남도'] and r.split(' / ')[1]==nn]
            return hits[0] if len(hits)==1 else None
        if s=='인천광역시' and nn in ['서해구','검단구','제물포구','영종구']:
            options=streetmap.get(street_key(a),[])
            if len(options)==1:return key(s,options[0])
            found=set()
            for dong in re.findall(r'([가-힣0-9]+동)',str(a)):
                found.update(dongmap.get(dong,[]))
            if len(found)==1:return key(s,found.pop())
        if nn.startswith('화성시'):nn='화성시'
        return match(s,nn,univ)
    d['road_region']=d.도로명주소.map(addr);d['lot_region']=d.지번주소.map(addr);d['region']=d.road_region.fillna(d.lot_region)
    d['address_conflict']=d.road_region.notna()&d.lot_region.notna()&d.road_region.ne(d.lot_region)
    # Infer opening-authority code only when every usable address under that code
    # points to one BC region. This repairs truncated and post-H1 renamed addresses.
    pairs=d.dropna(subset=['region'])[['개방자치단체코드','region']].drop_duplicates()
    code_map=pairs[pairs.groupby('개방자치단체코드').region.transform('nunique')==1].set_index('개방자치단체코드').region
    d['code_region']=d.개방자치단체코드.map(code_map);d['used_authority_code']=d.region.isna()&d.code_region.notna();d['region']=d.region.fillna(d.code_region)
    start=pd.Timestamp('2026-01-01');end=pd.Timestamp('2026-06-30')
    for c in ['인허가일자','인허가취소일자','폐업일자','휴업시작일자','휴업종료일자','재개업일자']:d[c+'_parsed']=pd.to_datetime(d[c],errors='coerce')
    normal=d.영업상태명.eq('영업/정상')&d.상세영업상태명.eq('정상영업')
    ceased=d.폐업일자_parsed.ge(start)|d.인허가취소일자_parsed.ge(start)
    suspended_later=d.영업상태명.eq('휴업')&d.휴업시작일자_parsed.gt(start)
    permitted=d.인허가일자_parsed.notna()&d.인허가일자_parsed.le(end)
    before_closed=(d.폐업일자_parsed.lt(start)|d.인허가취소일자_parsed.lt(start))&~d.재개업일자_parsed.between(start,end)
    whole_pause=d.휴업시작일자_parsed.le(start)&(d.휴업종료일자_parsed.isna()|d.휴업종료일자_parsed.ge(end))&~d.재개업일자_parsed.between(start,end)
    d['eligible_h1']=permitted&(normal|ceased|suspended_later)&~before_closed&~whole_pause&~d.상세영업상태명.eq('영업개시전')
    d['strict_current']=permitted&normal&~before_closed&~whole_pause
    d['name_type_conflict']=d.사업장명.fillna('').str.contains('시장|상가|아울렛|아웃렛|백화점|쇼핑센터',regex=True)
    d['narrow_type']=d.업태구분명.eq('대형마트')&~d.점포구분명.eq('준대규모점포')&~d.name_type_conflict
    d['broad_type']=d.narrow_type|(d.점포구분명.eq('준대규모점포')&d.업태구분명.isin(['대형마트','구분없음','그 밖의 대규모점포'])&~d.name_type_conflict)
    d['area_m2']=num(d.소재지면적).where(num(d.소재지면적)>0)
    d['narrow_selected']=d.eligible_h1&d.narrow_type;d['broad_selected']=d.eligible_h1&d.broad_type
    d['street_key']=d.도로명주소.map(street_key)
    d['normalized_name']=d.사업장명.fillna('').str.replace(r'\(주\)|주식회사|\s+','',regex=True)
    d['physical_key']=d.region.fillna('')+'|'+d.street_key+'|'+d.normalized_name
    d.loc[d.street_key.eq('')|d.region.isna(),'physical_key']=d.관리번호
    d['duplicate_physical_store']=False
    for selected in ['narrow_selected','broad_selected']:
        q=d[d[selected]].sort_values('strict_current',ascending=False)
        duplicates=q[q.physical_key.duplicated()].index;d.loc[duplicates,selected]=False;d.loc[duplicates,'duplicate_physical_store']=True
    save(d,'localdata_store_selection.csv')
    save(d.groupby(['영업상태명','상세영업상태명','업태구분명','점포구분명'],dropna=False).agg(rows=('관리번호','size'),h1_eligible=('eligible_h1','sum'),narrow_selected=('narrow_selected','sum'),broad_selected=('broad_selected','sum')).reset_index(),'localdata_status_audit.csv')
    rec=[]
    for r in base.region:
        z=d[d.region==r];v={'region':r}
        for mode in ['narrow','broad']:
            q=z[z[mode+'_selected']];v['mall_'+mode]=len(q);v['mall_'+mode+'_area_m2']=q.area_m2.sum(min_count=1) if len(q) else 0
            v['mall_'+mode+'_area_missing_rate']=q.area_m2.isna().mean() if len(q) else 0
        v['mall_strict']=z[z.strict_current&z.narrow_type].physical_key.nunique();rec.append(v)
    for mode in ['narrow','broad']:
        q=d[d[mode+'_selected']];AUDIT.append({'source':'LOCALDATA_'+mode,'rows':n,'selected':len(q),'unmatched_rows':q.region.isna().sum(),'area_missing_rate':q.area_m2.isna().mean(),'unit':'stores; area m2','note':'possible H1 operation, not verified daily exposure; no June closure history guaranteed'})
    GEO.extend({'source':'LOCALDATA','source_code':v.관리번호,'source_name':v.도로명주소 if pd.notna(v.도로명주소) else v.지번주소,'bc_region':v.region,'method':'authority_code_consensus' if v.used_authority_code else 'road_lot_March_street_dong_crosswalk','address_conflict':v.address_conflict} for _,v in d.iterrows())
    return pd.DataFrame(rec)
def main():
    TAB.mkdir(parents=True,exist_ok=True)
    hp=TAB/'protected_hashes_before.json'
    if not hp.exists():hp.write_text(json.dumps({str(p.relative_to(ROOT)):digest(p) for p in protected()},ensure_ascii=False,indent=2),encoding='utf-8')
    base=income(land_urban(region_base()))
    malls=localdata(base)
    if '--reuse-store-cache' in sys.argv:
        counts=pd.read_csv(TAB/'store_counts_by_definition.csv',dtype={'scope':str})
        oldgeo=pd.read_csv(TAB/'geography_crosswalk.csv');GEO.extend(oldgeo[oldgeo.source=='store'].to_dict('records'))
        oldaudit=pd.read_csv(TAB/'source_audit.csv');AUDIT.extend(oldaudit[oldaudit.source.str.contains('소상공인|store_deduplication',regex=True)].to_dict('records'))
    else:counts=stores(base)
    base=base.merge(malls,on='region',validate='one_to_one')
    for definition in ['narrow','broad']:
        w=counts[counts.definition==definition].pivot(index='region',columns='scope',values='stores').reindex(base.region).fillna(0)
        for scope in NAMES:
            base['store_'+definition+'_'+scope]=base['mall_'+definition].to_numpy() if scope=='4004' else (w[scope].to_numpy() if scope in w else 0)
    base['all_store_count']=base.region.map(counts[counts.scope=='all_store'].set_index('region').stores)
    base['admin_type']=np.select([base.CCG_NM.str.contains(' ')&base.CCG_NM.str.endswith('구'),base.CCG_NM.str.endswith('구'),base.CCG_NM.str.endswith('군')],['일반구','자치구','군'],default='시')
    for col in ['population','est_0','emp_0','all_store_count']+[f'store_{d}_{s}' for d in ['narrow','broad'] for s in NAMES]:
        base[col+'_density']=base[col]/base.area_km2
        if col.startswith('store_'):base[col+'_per10k']=base[col]/base.population*10000
    save(base,'external_region_features.csv');save(AUDIT,'source_audit.csv');save(GEO,'geography_crosswalk.csv')
    save([{'feature':c,'missing_n':base[c].isna().sum(),'missing_rate':base[c].isna().mean()} for c in base],'feature_missingness.csv')
    print('Preprocess complete',len(base),'regions',flush=True)
if __name__=='__main__':main()
