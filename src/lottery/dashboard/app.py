from __future__ import annotations

# ruff: noqa: E402  – sys.path must be patched before package imports so that
# `streamlit run src/lottery/dashboard/app.py` can resolve the lottery package.
import sys
from pathlib import Path

# Allow `streamlit run src/lottery/dashboard/app.py` to resolve the package.
SRC = Path(__file__).resolve().parents[2]
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd
import streamlit as st

from lottery.config import load_config
from lottery.data.repository import DrawRepository
from lottery.features.engineering import add_features
from lottery.stats import digits, frequency, pairs, sequence, suggest, summary
from lottery.dashboard.components.charts import (
    frequency_bar,
    heatmap_10x10,
    suggestion_bar,
    transition_heatmap,
)

DISCLAIMER = (
    "ℹ️ ข้อมูลนี้เป็นการวิเคราะห์เชิงสถิติย้อนหลังเพื่อการศึกษาเท่านั้น "
    "หวยเป็นการสุ่ม ผลในอดีตไม่สามารถทำนายผลในอนาคตได้"
)

TARGET_COLUMNS = {
    "เลขท้าย 2 ตัว (Last2)": "Last2",
    "เลขหน้า 3 ตัว #1 (Front3_1)": "Front3_1",
    "เลขท้าย 3 ตัว #1 (Back3_1)": "Back3_1",
    "รางวัลที่ 1 (FirstPrize)": "FirstPrize",
}


@st.cache_data
def get_data() -> pd.DataFrame:
    cfg = load_config()
    return add_features(DrawRepository(cfg.db_path).load())


def main() -> None:
    st.set_page_config(page_title="สถิติหวย", layout="wide")
    st.title("📊 วิเคราะห์สถิติหวยย้อนหลัง (พ.ศ. 2533–2569)")
    st.warning(DISCLAIMER)

    df = get_data()

    cfg = load_config()
    if st.sidebar.button("🔄 อัปเดตข้อมูลล่าสุด"):
        from lottery.data.updater import UpdateError, update_dataset

        repo = DrawRepository(cfg.db_path, cfg.csv_path)
        try:
            with st.spinner("กำลังดึงข้อมูลงวดล่าสุด..."):
                report = update_dataset(repo)
            get_data.clear()
            if report.added:
                st.sidebar.success(
                    f"เพิ่ม {report.added} งวด ({report.latest_before} → {report.latest_after})"
                )
            else:
                st.sidebar.info("ข้อมูลเป็นปัจจุบันแล้ว")
        except UpdateError as exc:
            st.sidebar.error(f"อัปเดตไม่สำเร็จ: {exc}")

    st.sidebar.header("ตัวกรอง")
    years = sorted(df["Year"].unique())
    year_range = st.sidebar.select_slider(
        "ช่วงปี (พ.ศ.)", options=years, value=(years[0], years[-1])
    )
    target_label = st.sidebar.selectbox("เลือกประเภทเลข", list(TARGET_COLUMNS))
    target = TARGET_COLUMNS[target_label]
    window = st.sidebar.number_input(
        "Hot/Cold เฉพาะ N งวดล่าสุด (0 = ทั้งหมด)", min_value=0, value=0, step=10
    )

    mask = (df["Year"] >= year_range[0]) & (df["Year"] <= year_range[1])
    view = df[mask]
    if view.empty:
        st.info("ไม่พบข้อมูลในช่วงที่เลือก")
        return

    series = view[target].dropna()
    if series.empty:
        st.info(f"ไม่มีข้อมูล {target_label} ในช่วงปีที่เลือก")
        return

    tabs = st.tabs(
        ["ภาพรวม", "ความถี่", "ช่วงห่าง", "หลักตัวเลข", "คู่/สามตัว", "แนวโน้ม", "ตัวเลขน่าสนใจ"]
    )

    with tabs[0]:
        counts = frequency.frequency(series).set_index("value")["count"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("จำนวนงวด", len(view))
        c2.metric("ช่วงวันที่", f"{view.iloc[0]['DrawDate']} → {view.iloc[-1]['DrawDate']}")
        c3.metric("Entropy", f"{summary.shannon_entropy(counts):.3f}")
        if target == "Last2":
            _, p_value = summary.chi_square_uniform(counts, 100)
            c4.metric("χ² p-value (uniform)", f"{p_value:.3f}")
        st.dataframe(view.tail(20))

    with tabs[1]:
        freq = frequency.frequency(series)
        st.plotly_chart(frequency_bar(freq, f"ความถี่ {target_label}"), use_container_width=True)
        if target == "Last2":
            st.plotly_chart(heatmap_10x10(freq, "ความถี่ 00–99"), use_container_width=True)
        hot_series = series.tail(window) if window else series
        hot, cold = frequency.hot_cold(hot_series)
        col_hot, col_cold = st.columns(2)
        col_hot.subheader("เลขมาบ่อย (Hot)")
        col_hot.dataframe(hot)
        col_cold.subheader("เลขมาน้อย (Cold)")
        col_cold.dataframe(cold)

    with tabs[2]:
        st.subheader("ช่วงห่างตั้งแต่ออกครั้งล่าสุด")
        st.dataframe(frequency.current_gap(series))

    with tabs[3]:
        st.plotly_chart(
            transition_heatmap(
                digits.position_distribution(series).T, "การกระจายตัวตามตำแหน่งหลัก"
            ),
            use_container_width=True,
        )
        st.subheader("คี่/คู่")
        st.dataframe(digits.odd_even_ratio(series))
        st.subheader("สูง/ต่ำ")
        st.dataframe(digits.high_low_ratio(series))

    with tabs[4]:
        st.subheader("ความถี่คู่ตัวเลข")
        st.dataframe(pairs.digit_pair_frequency(series).head(20))
        st.subheader("ความถี่สามตัวเลข")
        st.dataframe(pairs.digit_triple_frequency(series).head(20))

    with tabs[5]:
        st.subheader("Markov Transition (หลัก → หลักถัดไป)")
        st.plotly_chart(
            transition_heatmap(sequence.markov_transition(series), "Markov Transition"),
            use_container_width=True,
        )
        yearly = view.groupby("Year").size().rename("draws").reset_index()
        st.subheader("จำนวนงวดต่อปี")
        st.bar_chart(yearly, x="Year", y="draws")
        monthly = view.groupby("Month").size().rename("draws").reset_index()
        st.subheader("จำนวนงวดต่อเดือน")
        st.bar_chart(monthly, x="Month", y="draws")

    with tabs[6]:
        st.warning(suggest.DISCLAIMER)
        results = suggest.suggest_all(
            df, weights=cfg.weights, recent_window=cfg.recent_window, top_n=cfg.top_n
        )
        labels = {
            "last2": "เลขท้าย 2 ตัว",
            "back3": "เลขท้าย 3 ตัว",
            "front3": "เลขหน้า 3 ตัว",
            "firstprize_last3": "3 ตัวท้ายรางวัลที่ 1",
        }
        for cat, label in labels.items():
            st.subheader(label)
            cand = results[cat]
            if cand.empty:
                st.info("ไม่มีข้อมูลเพียงพอสำหรับประเภทนี้")
                continue
            st.plotly_chart(
                suggestion_bar(cand, f"คะแนนเชิงสถิติ {label}"),
                use_container_width=True,
            )
            st.dataframe(cand)
        st.subheader("ความถี่ตัวเลขแต่ละหลัก (รางวัลที่ 1)")
        st.dataframe(results["firstprize_digits"])


if __name__ == "__main__":
    main()
