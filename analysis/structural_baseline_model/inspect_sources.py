from pathlib import Path
import sys, hashlib, json, csv
from zipfile import ZipFile
import xml.etree.ElementTree as ET
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
NS='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
def rows(p):
    with ZipFile(p) as z:
        ss=[''.join(t.text or '' for t in e.iter(NS+'t')) for e in ET.fromstring(z.read('xl/sharedStrings.xml'))] if 'xl/sharedStrings.xml' in z.namelist() else []
        for row in ET.fromstring(z.read('xl/worksheets/sheet1.xml')).iter(NS+'row'):
            d={}
            for c in row:
                v=c.find(NS+'v');v=v.text if v is not None else ''.join(t.text or '' for t in c.iter(NS+'t'))
                d[c.attrib['r']]=ss[int(v)] if c.attrib.get('t')=='s' else v
            yield d
def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(2**22),b''):h.update(b)
    return h.hexdigest()
def protected():
    dirs=[ROOT/'data/external/raw']+[p for p in (ROOT/'analysis').iterdir() if p.is_dir() and p!=OUT]
    return [ROOT/'data/ABP_CONTEST_DATA.csv',ROOT/'data/external/README.md']+[p for d in dirs for p in d.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
if __name__=='__main__':
    (OUT/'tables').mkdir(parents=True,exist_ok=True)
    p=OUT/'tables/protected_hashes_before.json'
    if not p.exists():p.write_text(json.dumps({str(p.relative_to(ROOT)):digest(p) for p in protected()},ensure_ascii=False,indent=2),encoding='utf-8')
    import pandas as pd
    raw=ROOT/'data/external/raw'
    for p in raw.glob('nts_*.xlsx'):
        print('\nXLSX',p.name)
        rr=list(rows(p));print('rows',len(rr));print(rr[:13]);print(rr[-3:])
    for p in list(raw.glob('kosis_*.csv'))+[raw/'생활_대규모점포.csv']+list((raw/'소상공인시장진흥공단_상가(상권)정보_20260331').glob('*.csv'))[:1]:
        for enc in ['utf-8-sig','cp949']:
            try:d=pd.read_csv(p,encoding=enc,nrows=4);break
            except UnicodeDecodeError:pass
        print('\nCSV',p.name,enc);print(d.to_string(index=False))
    for f in ['region_industry_cross_section_main.csv','region_fold_assignments.csv','model_feature_dictionary.csv']:
        d=pd.read_csv(ROOT/'analysis/business_mobility_explanatory_power/tables'/f);print(f,d.shape);print(d.head(2).to_string(index=False))
