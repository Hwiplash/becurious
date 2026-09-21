"""Partial inference survives the production adapter, chart and Streamlit path."""
import unittest
from pathlib import Path
import numpy as np
from src.total_market import load_total_market_regions, diagnostic_series
from src.charts import consumption_diagnostic_chart


class PartialMarketTests(unittest.TestCase):
    def test_partial_adapter_band_and_missing_actual_gaps(self):
        seen=0
        for record in load_total_market_regions().values():
            scopes={r['scope'] for r in record['monthly'] if r['band_status']=='partial_observation_inference'}
            for scope in scopes:
                rows=[r for r in record['monthly'] if r['scope']==scope]
                f=diagnostic_series(record['sido'],record['sigungu'],rows[0]['industry'])
                self.assertEqual(len(f),6)
                self.assertTrue(f.band_status.eq('partial_observation_inference').all())
                self.assertTrue(f.prediction_interval_available.all())
                self.assertTrue(f.expected_amt.notna().all())
                self.assertTrue(f.actual_amt.isna().any())
                self.assertTrue(f.band_message.str.contains('별도 검증하지 않았습니다').all())
                for t in ['amt','cnt']:
                    fig=consumption_diagnostic_chart(f,t)
                    for i,c in [(0,'lower90_'),(1,'upper90_'),(2,'expected_'),(3,'actual_')]:
                        np.testing.assert_allclose(fig.data[i].y,f[c+t],equal_nan=True)
                    self.assertFalse(fig.data[3].connectgaps)
                seen+=1
        self.assertGreater(seen,0)

    def test_partial_warning_displayed_in_streamlit(self):
        from streamlit.testing.v1 import AppTest
        record=next(r for r in load_total_market_regions().values() if any(m['band_status']=='partial_observation_inference' for m in r['monthly']))
        row=next(m for m in record['monthly'] if m['band_status']=='partial_observation_inference')
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=90)
        app.session_state['region_view']='local'
        app.session_state['selected_sido']=record['sido']
        app.session_state['selected_ccg']=record['sigungu']
        app.run()
        self.assertEqual(len(app.exception),0,str(app.exception))
        selector=app.selectbox(key='region_industry_filter')
        option=next(v for v in selector.options if v.replace(' ','')==row['industry'].replace(' ',''))
        selector.set_value(option).run()
        self.assertEqual(len(app.exception),0,str(app.exception))
        self.assertTrue(any('부분관측 집단의 90% 포함률은 별도 검증하지 않았습니다' in c.value for c in app.caption))


if __name__=='__main__':unittest.main()
