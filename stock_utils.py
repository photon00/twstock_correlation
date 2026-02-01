"""
台股相關係數計算工具
使用 yfinance 同時抓取多支股票，twstock 提供電子股清單與名稱
"""

import datetime
from typing import Optional

import pandas as pd
import yfinance as yf
import twstock

# 電子股產業分類 (排除傳產)
ELECTRONICS_GROUPS = {
    "半導體業",
    "電腦及週邊設備業",
    "電子零組件業",
    "光電業",
    "通信網路業",
    "電子通路業",
    "資訊服務業",
    "其他電子業",
    "數位雲端",
}


def _to_yf_ticker(sid: str) -> str:
    """將台股代號轉為 yfinance 格式：上市 .TW、上櫃 .TWO"""
    try:
        info = twstock.codes.get(sid)
        if info and hasattr(info, "market"):
            return f"{sid}.TWO" if info.market == "上櫃" else f"{sid}.TW"
    except Exception:
        pass
    return f"{sid}.TW"  # 預設上市


def get_electronics_stock_codes(group: Optional[str] = None) -> list[str]:
    """取得電子股的股票代號，可依產業分類篩選"""
    codes = []
    for code, info in twstock.codes.items():
        if not hasattr(info, "type") or info.type != "股票":
            continue
        if not hasattr(info, "group"):
            continue
        if info.group not in ELECTRONICS_GROUPS:
            continue
        if group and group != "全選" and info.group != group:
            continue
        codes.append(code)
    return sorted(codes)


def get_stock_name(sid: str) -> str:
    """取得股票名稱"""
    try:
        return twstock.codes[sid].name if sid in twstock.codes else sid
    except Exception:
        return sid


def get_stock_group(sid: str) -> str:
    """取得股票類型（產業分類）"""
    try:
        return twstock.codes[sid].group if sid in twstock.codes and hasattr(twstock.codes[sid], "group") else ""
    except Exception:
        return ""


def fetch_stocks_prices(
    sids: list[str], days_back: int = 180
) -> dict[str, pd.DataFrame]:
    """
    一次擷取多支股票歷史股價 (使用 yfinance)
    回傳 {sid: DataFrame with date, close}
    """
    if not sids:
        return {}

    sid_to_ticker = {s: _to_yf_ticker(s) for s in sids}
    tickers = list(sid_to_ticker.values())
    end = datetime.datetime.today()
    start = end - datetime.timedelta(days=days_back)

    try:
        df = yf.download(
            tickers,
            start=start,
            end=end,
            progress=False,
            group_by="ticker",
            auto_adjust=True,
            threads=True,
        )
    except Exception:
        return {}

    if df.empty:
        return {}

    result = {}
    # 單一股票時 yfinance 回傳扁平 columns
    if len(sids) == 1:
        sid = sids[0]
        closes = df["Close"] if "Close" in df.columns else None
        if closes is not None:
            out = pd.DataFrame({"date": df.index, "close": closes.values})
            out["date"] = pd.to_datetime(out["date"])
            out = out.dropna().drop_duplicates(subset=["date"]).sort_values("date")
            result[sid] = out
        return result

    # 多股票：MultiIndex columns (ticker, 'Close')
    for sid, ticker in sid_to_ticker.items():
        col = (ticker, "Close")
        if col not in df.columns:
            continue
        out = pd.DataFrame({"date": df.index, "close": df[col].values})
        out["date"] = pd.to_datetime(out["date"])
        out = out.dropna().drop_duplicates(subset=["date"]).sort_values("date")
        result[sid] = out

    return result


def fetch_stock_prices(sid: str, months_back: int = 7) -> Optional[pd.DataFrame]:
    """擷取單一股票歷史股價（相容介面）"""
    days = months_back * 31
    result = fetch_stocks_prices([sid], days_back=days)
    return result.get(sid)


def calculate_correlations(
    target_sid: str,
    electronics_codes: Optional[list[str]] = None,
    limit: Optional[int] = None,
) -> pd.DataFrame:
    """
    計算給定股票與其他電子股的相關係數（20天、60天、120天）
    使用 yfinance 一次抓取所有股票，大幅加快速度
    """
    if electronics_codes is None:
        electronics_codes = get_electronics_stock_codes()
    if limit:
        electronics_codes = electronics_codes[:limit]

    # 排除目標股票
    others = [s for s in electronics_codes if s != target_sid]
    if not others:
        return pd.DataFrame()

    # 一次抓取目標 + 其他股票
    all_sids = [target_sid] + others
    prices_dict = fetch_stocks_prices(all_sids, days_back=210)

    target_df = prices_dict.get(target_sid)
    if target_df is None or len(target_df) < 20:
        return pd.DataFrame()

    target_df = target_df.rename(columns={"close": "target"}).set_index("date")

    results = []
    for sid in others:
        df = prices_dict.get(sid)
        if df is None or len(df) < 20:
            continue

        df = df.rename(columns={"close": sid}).set_index("date")
        merged = target_df.join(df, how="inner").dropna().tail(120)

        if len(merged) < 20:
            continue

        corr_20 = (
            merged["target"].tail(20).corr(merged[sid].tail(20))
            if len(merged) >= 20
            else None
        )
        corr_60 = (
            merged["target"].tail(60).corr(merged[sid].tail(60))
            if len(merged) >= 60
            else None
        )
        corr_120 = merged["target"].corr(merged[sid]) if len(merged) >= 120 else None

        results.append(
            {
                "代號": sid,
                "名稱": get_stock_name(sid),
                "120天相關係數": round(corr_120, 4) if corr_120 is not None else None,
                "20天相關係數": round(corr_20, 4) if corr_20 is not None else None,
                "60天相關係數": round(corr_60, 4) if corr_60 is not None else None,
                "股票類型": get_stock_group(sid),
            }
        )

    df = pd.DataFrame(results).sort_values("120天相關係數", ascending=False)
    df.insert(0, "序號", range(1, len(df) + 1))
    return df


def get_two_stocks_comparison(
    sid1: str, sid2: str, days: int = 120
) -> tuple[
    Optional[pd.DataFrame],
    Optional[pd.DataFrame],
    Optional[pd.DataFrame],
    Optional[pd.DataFrame],
]:
    """
    取得兩支股票最近 N 天的股價與價比
    使用 yfinance 一次抓取
    回傳 (price_df, ratio_df, merged, detail_table_df)
    detail_table_df: 含股價、股價變動、股價相除的明細表
    """
    days_back = max(180, days + 60)
    prices_dict = fetch_stocks_prices([sid1, sid2], days_back=days_back)

    df1 = prices_dict.get(sid1)
    df2 = prices_dict.get(sid2)
    if df1 is None or df2 is None:
        return None, None, None, None

    col1 = f"{sid1}_{get_stock_name(sid1)}"
    col2 = f"{sid2}_{get_stock_name(sid2)}"
    df1 = df1.rename(columns={"close": col1})
    df2 = df2.rename(columns={"close": col2})

    merged = df1.merge(df2, on="date", how="inner")
    merged = merged.dropna().sort_values("date").tail(days)

    if merged.empty or len(merged) < 10:
        return None, None, None, None

    merged["價比"] = merged[col1] / merged[col2]
    merged["股價變動1"] = merged[col1].diff()
    merged["股價變動2"] = merged[col2].diff()
    if len(merged) >= 20:
        merged["20日均比"] = merged["價比"].rolling(20).mean()
    if len(merged) >= 60:
        merged["60日均比"] = merged["價比"].rolling(60).mean()
    if len(merged) >= 120:
        merged["120日均比"] = merged["價比"].rolling(120).mean()

    price_df = merged[["date", col1, col2]].copy()
    ratio_df = merged[["date", "價比"]].copy()

    # 建立明細表：股價、股價變動、股價相除、均線（列為類型，欄為日期，由新到舊）
    merged_rev = merged.sort_values("date", ascending=False)
    date_strs = merged_rev["date"].dt.strftime("%m/%d").tolist()
    types_list = [
        f"股價 {get_stock_name(sid1)}",
        f"股價 {get_stock_name(sid2)}",
        f"股價變動 {get_stock_name(sid1)}",
        f"股價變動 {get_stock_name(sid2)}",
        "股價相除",
    ]
    if "20日均比" in merged.columns:
        types_list.append("20日均比")
    if "60日均比" in merged.columns:
        types_list.append("60日均比")
    if "120日均比" in merged.columns:
        types_list.append("120日均比")

    detail_data = {"類型": types_list}
    for j, d in enumerate(date_strs):
        row_vals = [
            merged_rev[col1].iloc[j],
            merged_rev[col2].iloc[j],
            merged_rev["股價變動1"].iloc[j],
            merged_rev["股價變動2"].iloc[j],
            merged_rev["價比"].iloc[j],
        ]
        if "20日均比" in merged.columns:
            row_vals.append(merged_rev["20日均比"].iloc[j])
        if "60日均比" in merged.columns:
            row_vals.append(merged_rev["60日均比"].iloc[j])
        if "120日均比" in merged.columns:
            row_vals.append(merged_rev["120日均比"].iloc[j])
        detail_data[d] = row_vals
    detail_table = pd.DataFrame(detail_data)

    return price_df, ratio_df, merged, detail_table
