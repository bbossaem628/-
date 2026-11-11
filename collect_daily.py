import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from io import StringIO
import pandas as pd
import requests
import yfinance as yf

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
CSV = DATA_DIR / "economic_history.csv"

YF = {
    "원/달러 환율": "KRW=X", "달러인덱스": "DX-Y.NYB",
    "코스피": "^KS11", "코스닥": "^KQ11", "다우존스": "^DJI",
    "S&P 500": "^GSPC", "나스닥 종합": "^IXIC",
    "비트코인": "BTC-USD", "이더리움": "ETH-USD",
}
FRED = {
    "한국 기준금리": "IRSTCI01KRM156N",
    "미국 기준금리": "DFF",
    "미국 2년 국채금리": "DGS2",
    "미국 10년 국채금리": "DGS10",
}

def load_old():
    if CSV.exists():
        return pd.read_csv(CSV)
    return pd.DataFrame(columns=["date", "indicator", "value", "source", "status"])

def main():
    start = datetime.now(timezone.utc) - timedelta(days=420)
    rows, errors = [], []
    for name, ticker in YF.items():
        try:
            data = yf.download(ticker, start=start.strftime("%Y-%m-%d"),
                               auto_adjust=False, progress=False, threads=False)
            if data is None or data.empty:
                raise RuntimeError("빈 응답")
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            col = "Adj Close" if "Adj Close" in data.columns else "Close"
            for date, value in data[col].dropna().items():
                rows.append({"date": pd.Timestamp(date).date().isoformat(),
                             "indicator": name, "value": float(value),
                             "source": f"Yahoo Finance {ticker}", "status": "자동수집"})
        except Exception as e:
            errors.append(f"{name}: {e}")

    for name, series in FRED.items():
        try:
            url = "https://fred.stlouisfed.org/graph/fredgraph.csv"
            resp = requests.get(url, params={"id": series, "cosd": start.strftime("%Y-%m-%d")},
                                timeout=30)
            resp.raise_for_status()
            data = pd.read_csv(StringIO(resp.text))
            data.columns = ["date", "value"]
            data["value"] = pd.to_numeric(data["value"], errors="coerce")
            data = data.dropna()
            for _, r in data.iterrows():
                rows.append({"date": pd.Timestamp(r["date"]).date().isoformat(),
                             "indicator": name, "value": float(r["value"]),
                             "source": f"FRED {series}", "status": "자동수집"})
        except Exception as e:
            errors.append(f"{name}: {e}")

    # Optional ECOS integration: add ECOS_API_KEY and exact ECOS item/table codes
    # as GitHub repository secrets after confirming the desired official series.
    old = load_old()
    if rows:
        new = pd.DataFrame(rows)
        out = pd.concat([old, new], ignore_index=True)
        out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        out = out.dropna(subset=["date", "value"])
        out = out.drop_duplicates(["date", "indicator"], keep="last")
        out = out.sort_values(["date", "indicator"])
        out.to_csv(CSV, index=False, encoding="utf-8-sig")

    print(f"Collected {len(rows)} observations at {datetime.now().isoformat()}")
    if errors:
        print("Collection errors:")
        for error in errors:
            print(error)

if __name__ == "__main__":
    main()
