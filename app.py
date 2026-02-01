"""
台股相關係數分析系統 - Streamlit 應用
"""

import scheduler_config  # noqa: F401 - starts twstock update scheduler

import streamlit as st
import pandas as pd
import altair as alt

from stock_utils import (
    get_electronics_stock_codes,
    get_stock_name,
    calculate_correlations,
    get_two_stocks_comparison,
    ELECTRONICS_GROUPS,
)

st.set_page_config(page_title="台股相關係數分析", layout="wide")
st.title("台股相關係數分析系統")
st.caption("資料來源：twstock, yahoo finance | 僅涵蓋電子股")

# 側邊欄：選擇功能
page = st.sidebar.radio(
    "選擇功能",
    ["表一：單一股票相關係數", "表二：雙股票股價比較"],
    index=0,
)

# 表二用全部電子股
electronics_codes_all = get_electronics_stock_codes()

if page == "表一：單一股票相關係數":
    st.header("表一：單一股票與其他電子股相關係數")

    group_options = ["全選"] + sorted(ELECTRONICS_GROUPS)
    selected_group = st.selectbox(
        "選擇產業分類",
        options=group_options,
        index=0,
        key="table1_group",
    )
    group_filter = None if selected_group == "全選" else selected_group
    electronics_codes = get_electronics_stock_codes(group=group_filter)
    # 分析的股票可選全部電子股，不受產業分類限制
    stock_options_all = {f"{c} {get_stock_name(c)}": c for c in electronics_codes_all}

    selected = st.selectbox(
        "選擇要分析的股票",
        options=list(stock_options_all.keys()),
        index=0,
        key="table1_stock",
    )
    limit = st.number_input(
        "計算股票數量 (0=全部，可設較小值加快計算)",
        min_value=0,
        max_value=max(len(electronics_codes), 1),
        value=min(50, len(electronics_codes)),
        step=10,
        key="table1_limit",
    )
    target_sid = stock_options_all[selected]

    if st.button("計算相關係數", key="table1_btn"):
        codes_limit = None if limit == 0 else limit
        with st.spinner("計算中..."):
            df = calculate_correlations(
                target_sid, electronics_codes=electronics_codes, limit=codes_limit
            )

        if df.empty:
            st.warning("無法取得足夠資料，請稍後再試")
        else:
            corr_cols = ["120天相關係數", "20天相關係數", "60天相關係數"]
            styled = (
                df.style.background_gradient(
                    subset=corr_cols,
                    cmap="RdYlGn",
                    vmin=-1,
                    vmax=1,
                )
                .format({"序號": "{:.0f}", **{c: "{:.4f}" for c in corr_cols}})
            )
            st.dataframe(styled, use_container_width=True, hide_index=True)
            st.caption(
                f"共 {len(df)} 檔電子股"
                + (f"（{selected_group}）" if selected_group != "全選" else "")
                + "，依 120 天相關係數由高到低排序（綠=正相關、紅=負相關）"
            )

else:
    stock_options = {f"{c} {get_stock_name(c)}": c for c in electronics_codes_all}
    days_options = {"120 天": 120, "60 天": 60, "20 天": 20}
    selected_days_label = st.selectbox(
        "選擇期間",
        options=list(days_options.keys()),
        index=0,
        key="table2_days",
    )
    days = days_options[selected_days_label]
    st.header(f"表二：雙股票股價比較 (最近 {days} 天)")

    col1, col2 = st.columns(2)
    with col1:
        stock1 = st.selectbox("股票一", options=list(stock_options.keys()), key="s1")
    with col2:
        stock2 = st.selectbox("股票二", options=list(stock_options.keys()), key="s2")

    sid1 = stock_options[stock1]
    sid2 = stock_options[stock2]

    if sid1 == sid2:
        st.warning("請選擇兩支不同的股票")
    elif st.button("顯示股價與價比圖表"):
        with st.spinner("載入股價資料..."):
            price_df, ratio_df, merged, detail_table = get_two_stocks_comparison(
                sid1, sid2, days=days
            )

        if price_df is None:
            st.error("無法取得股價資料，請稍後再試")
        else:
            # 股價走勢圖
            st.subheader("股價走勢")

            price_cols = [c for c in price_df.columns if c != "date"]
            chart_data = price_df.melt(
                id_vars="date", value_vars=price_cols, var_name="股票", value_name="收盤價"
            )

            chart = (
                alt.Chart(chart_data)
                .mark_line()
                .encode(
                    x=alt.X(
                        "date:T",
                        title="日期",
                        axis=alt.Axis(format="%m/%d"),
                    ),
                    y=alt.Y("收盤價:Q", title="收盤價"),
                    color="股票:N",
                )
                .properties(height=350)
                .interactive()
            )
            st.altair_chart(chart, use_container_width=True)

            # 價比走勢圖（含 20/60/120 天均線）
            st.subheader("股價相除比較 (價比)")

            ratio_with_ma = ratio_df.copy()
            if len(ratio_with_ma) >= 20:
                ratio_with_ma["20日均比"] = ratio_with_ma["價比"].rolling(20).mean()
            if len(ratio_with_ma) >= 60:
                ratio_with_ma["60日均比"] = ratio_with_ma["價比"].rolling(60).mean()
            if len(ratio_with_ma) >= 120:
                ratio_with_ma["120日均比"] = ratio_with_ma["價比"].rolling(120).mean()

            ratio_melt = ratio_with_ma.melt(
                id_vars="date",
                value_vars=[c for c in ratio_with_ma.columns if c != "date"],
                var_name="類型",
                value_name="數值",
            ).dropna()

            ratio_chart = (
                alt.Chart(ratio_melt)
                .mark_line()
                .encode(
                    x=alt.X(
                        "date:T",
                        title="日期",
                        axis=alt.Axis(format="%m/%d"),
                    ),
                    y=alt.Y("數值:Q", title="價比"),
                    color=alt.Color(
                        "類型:N",
                        scale=alt.Scale(
                            domain=["價比", "20日均比", "60日均比", "120日均比"],
                            range=["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4"],
                        ),
                    )
                )
                .properties(height=300)
                .interactive()
            )
            st.altair_chart(ratio_chart, use_container_width=True)

            # 資料表格：股價、股價變動、股價相除
            with st.expander("檢視原始資料"):
                if detail_table is not None:
                    # 股價變動列加上顏色（正綠負紅），只套用在第 3、4 列
                    def highlight_diff_rows(df):
                        arr = pd.DataFrame("", index=df.index, columns=df.columns)
                        for c in df.columns:
                            if c == "類型":
                                continue
                            for i in [2, 3]:  # 股價變動 兩列
                                val = df[c].iloc[i]
                                if pd.notna(val):
                                    try:
                                        v = float(val)
                                        if v > 0:
                                            arr.iloc[i, df.columns.get_loc(c)] = (
                                                "background-color: #d4edda; color: black"
                                            )
                                        elif v < 0:
                                            arr.iloc[i, df.columns.get_loc(c)] = (
                                                "background-color: #f8d7da; color: black"
                                            )
                                    except (ValueError, TypeError):
                                        pass
                        return arr

                    value_cols = [c for c in detail_table.columns if c != "類型"]
                    def _fmt(x):
                        return f"{x:.2f}" if pd.notna(x) and isinstance(x, (int, float)) else ""
                    fmt = {c: _fmt for c in value_cols}
                    styled_detail = detail_table.style.apply(
                        highlight_diff_rows, axis=None
                    ).format(fmt)
                    st.dataframe(
                        styled_detail, use_container_width=True, hide_index=True
                    )
                else:
                    st.dataframe(price_df, use_container_width=True)
