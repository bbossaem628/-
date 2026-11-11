import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
from datetime import datetime, timedelta

BASE = Path(__file__).parent
DATA = BASE / "data" / "economic_history.csv"

st.set_page_config(page_title="경제지표 모니터링", page_icon="📈", layout="wide")
st.title("📈 경제지표 모니터링 대시보드")
st.caption("매일 축적되는 금리·환율·주식·가상자산 데이터를 한 화면에서 확인합니다.")

META = {
    "한국 기준금리": ("금리·채권", "%"),
    "국고채 3년물": ("금리·채권", "%"),
    "미국 기준금리": ("금리·채권", "%"),
    "미국 2년 국채금리": ("금리·채권", "%"),
    "미국 10년 국채금리": ("금리·채권", "%"),
    "원/달러 환율": ("환율·달러", "원"),
    "달러인덱스": ("환율·달러", "지수"),
    "코스피": ("국내 주식", "지수"),
    "코스닥": ("국내 주식", "지수"),
    "다우존스": ("미국 주식", "지수"),
    "S&P 500": ("미국 주식", "지수"),
    "나스닥 종합": ("미국 주식", "지수"),
    "비트코인": ("가상자산·반도체", "USD"),
    "이더리움": ("가상자산·반도체", "USD"),
    "반도체 D램 가격": ("가상자산·반도체", "USD"),
}

@st.cache_data(ttl=300)
def load_data():
    if not DATA.exists():
        return pd.DataFrame(columns=["date", "indicator", "value", "source", "status"])
    df = pd.read_csv(DATA)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.dropna(subset=["date", "value"])

df = load_data()

with st.sidebar:
    st.header("조회 설정")
    period = st.selectbox("조회 기간", ["1개월", "3개월", "6개월", "1년", "전체"], index=2)
    days = {"1개월": 31, "3개월": 92, "6개월": 183, "1년": 366, "전체": 100000}[period]
    st.caption("데이터는 GitHub Actions가 매일 정해진 시간에 수집하도록 구성됩니다.")
    if st.button("화면 데이터 새로고침"):
        st.cache_data.clear()
        st.rerun()

if df.empty:
    st.warning("아직 수집된 데이터가 없습니다. GitHub 저장소에 배포한 뒤 Actions의 'Daily economic data collection'을 한 번 실행해 주세요.")
else:
    df = df.sort_values("date")
    latest_day = df["date"].max().date()
    st.caption(f"마지막 데이터 날짜: {latest_day} · 마지막 수집 기록은 저장소의 Actions에서 확인할 수 있습니다.")

    latest_rows = []
    for name in META:
        x = df[df.indicator == name].sort_values("date")
        if x.empty:
            continue
        last = x.iloc[-1]
        prev = x.iloc[-2] if len(x) > 1 else None
        delta = float(last.value - prev.value) if prev is not None else None
        pct = delta / float(prev.value) * 100 if prev is not None and float(prev.value) != 0 else None
        latest_rows.append((name, float(last.value), delta, pct, last.date.date(), META[name][1]))

    st.subheader("최신 지표")
    cols = st.columns(3)
    for i, (name, value, delta, pct, date, unit) in enumerate(latest_rows):
        delta_label = None if pct is None else f"{pct:+.2f}%"
        with cols[i % 3]:
            st.metric(name, f"{value:,.4f} {unit}" if unit == "%" else f"{value:,.2f} {unit}", delta=delta_label)
            st.caption(f"기준일: {date}")

    st.divider()
    groups = list(dict.fromkeys(v[0] for v in META.values()))
    group = st.selectbox("분야", groups)
    options = [n for n, (g, _) in META.items() if g == group]
    selected = st.multiselect("그래프에 표시할 지표", options, default=options[:min(4, len(options))])
    chart = df[df.indicator.isin(selected)].copy()
    if period != "전체":
        chart = chart[chart.date >= pd.Timestamp.now().normalize() - pd.Timedelta(days=days)]
    if not chart.empty:
        chart["기준일=100"] = chart.groupby("indicator")["value"].transform(
            lambda s: s / s.iloc[0] * 100 if len(s) and s.iloc[0] else s
        )
        fig = px.line(chart, x="date", y="기준일=100", color="indicator",
                      title="기간 첫 관측값을 100으로 환산한 추세 비교")
        fig.update_layout(hovermode="x unified", xaxis_title="날짜", yaxis_title="기준일=100")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("단위가 다른 지표의 방향을 비교하기 위한 지수화 그래프입니다. 금리·가격의 절대 수준 비교에는 각 지표별 그래프를 사용하세요.")

    st.subheader("지표별 원자료")
    chosen = st.selectbox("원자료 확인", list(META.keys()))
    raw = df[df.indicator == chosen].sort_values("date", ascending=False)
    if raw.empty:
        st.info("아직 이 지표의 데이터가 연결되지 않았습니다.")
    else:
        st.line_chart(raw.sort_values("date").set_index("date")["value"])
        st.dataframe(raw[["date", "value", "source", "status"]], use_container_width=True, hide_index=True)

    st.subheader("수집 상태")
    latest_status = df.sort_values("date").groupby("indicator", as_index=False).tail(1)
    st.dataframe(latest_status[["indicator", "date", "source", "status"]].sort_values("indicator"),
                 use_container_width=True, hide_index=True)

st.divider()
st.subheader("데이터 범위와 유의사항")
st.markdown("""
- **자동 수집 가능(기본 설정)**: 원/달러 환율, 달러인덱스, 코스피·코스닥, 다우존스, S&P 500, 나스닥 종합, 비트코인, 이더리움(Yahoo Finance); 미국 기준금리와 미 2년·10년 국채금리(FRED).
- **한국 기준금리**: FRED의 한국 금리 참고계열을 수집합니다. 한국은행의 공식 기준금리 발표값과 대조해 확정 연결해야 합니다.
- **국고채 3년물**: 한국은행 ECOS API 인증키와 통계 항목 코드 설정이 필요합니다. 키를 설정하기 전까지 자동수집 대상에서 빠집니다.
- **D램 가격**: 신뢰할 수 있는 공개 무료 일별 API가 제한적입니다. TrendForce/DRAMeXchange 등 이용 가능한 라이선스 또는 제공 API가 확보되면 연결해야 합니다. 이 버전은 임의의 값을 생성하지 않습니다.
- 금융 데이터는 휴장일, 발표주기, 제공처 정책에 따라 지연·누락·수정될 수 있습니다. 투자 판단 전 원 출처를 확인하세요.
""")
if not df.empty:
    st.download_button("누적 데이터 CSV 다운로드", df.to_csv(index=False).encode("utf-8-sig"),
                       "economic_history.csv", "text/csv")
