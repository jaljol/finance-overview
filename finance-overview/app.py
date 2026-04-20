import streamlit as st
import pandas as pd
from supabase import create_client

# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="Privat økonomi",
    layout="wide",
    page_icon="💳"
)

# =========================================================
# GLOBAL STYLES (fintech look)
# =========================================================
st.markdown("""
<style>
/* ---------- Base ---------- */
html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
                 Roboto, Oxygen, Ubuntu, Cantarell, "Helvetica Neue", sans-serif;
    background-color: #f8fafc;
}

/* ---------- Headings ---------- */
h1 {
    font-size: 2.4rem;
    font-weight: 700;
    margin-bottom: 0.2rem;
}
h2 {
    margin-top: 3rem;
    margin-bottom: 1rem;
    font-weight: 600;
}
h3 {
    margin-top: 1.5rem;
    font-weight: 600;
}

/* ---------- Cards ---------- */
.card {
    background-color: #ffffff;
    border-radius: 18px;
    padding: 1.4rem 1.6rem;
    box-shadow: 0 10px 30px rgba(0,0,0,0.06);
    border: 1px solid #e5e7eb;
}

/* ---------- Metrics ---------- */
.metric-title {
    font-size: 0.85rem;
    color: #6b7280;
    margin-bottom: 0.3rem;
}
.metric-value {
    font-size: 1.6rem;
    font-weight: 700;
}

/* ---------- Amounts ---------- */
.amount-positive {
    color: #16a34a;
    font-weight: 700;
}
.amount-negative {
    color: #dc2626;
    font-weight: 700;
}

/* ---------- Badges ---------- */
.badge {
    display: inline-block;
    padding: 0.25rem 0.65rem;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
}
.badge-auto {
    background-color: #e0f2fe;
    color: #0369a1;
}
.badge-manual {
    background-color: #dcfce7;
    color: #166534;
}

/* ---------- Transaction card ---------- */
.tx-card {
    margin-bottom: 1rem;
}
.tx-title {
    font-weight: 600;
    margin-bottom: 0.15rem;
}
.tx-date {
    font-size: 0.8rem;
    color: #6b7280;
}

</style>
""", unsafe_allow_html=True)

# =========================================================
# HEADER
# =========================================================
st.title("💳 Min privatøkonomi")
st.caption("Privat overblik · Automatisk kategorisering · Manuel læring")

# =========================================================
# SUPABASE
# =========================================================
supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)
USER_ID = "janus"

# =========================================================
# CATEGORIES
# =========================================================
categories = (
    supabase
    .table("categories")
    .select("id, name")
    .eq("is_active", True)
    .execute()
    .data
)

cat_name_to_id = {c["name"]: c["id"] for c in categories}
cat_id_to_name = {c["id"]: c["name"] for c in categories}
category_names = sorted(cat_name_to_id.keys())

# =========================================================
# DASHBOARD METRICS (placeholder)
# =========================================================
st.markdown("## 📊 Overblik")

m1, m2, m3 = st.columns(3)

with m1:
    st.markdown("""
    <div class="card">
        <div class="metric-title">Saldo (30 dage)</div>
        <div class="metric-value amount-positive">12.345 kr</div>
    </div>
    """, unsafe_allow_html=True)

with m2:
    st.markdown("""
    <div class="card">
        <div class="metric-title">Udgifter</div>
        <div class="metric-value amount-negative">−4.321 kr</div>
    </div>
    """, unsafe_allow_html=True)

with m3:
    st.markdown("""
    <div class="card">
        <div class="metric-title">Kategoriseret</div>
        <div class="metric-value">87 %</div>
    </div>
    """, unsafe_allow_html=True)

# =========================================================
# CSV UPLOAD
# =========================================================
st.markdown("## 📁 Importér transaktioner")

with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)

    file = st.file_uploader(
        "Træk din CSV hertil eller klik for at vælge",
        type="csv"
    )

    if file:
        df_raw = pd.read_csv(file, sep=";", header=None, dtype=str)

        df = pd.DataFrame({
            "own_description": df_raw[0].fillna(""),
            "orig_description": df_raw[1].fillna(""),
            "amount_raw": df_raw[4],
            "date_raw": df_raw[8],
        })

        df["amount"] = (
            df["amount_raw"]
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
            .astype(float)
        )

        df["date_booked"] = pd.to_datetime(
            df["date_raw"], format="%d-%m-%Y", errors="coerce"
        ).dt.date

        df["raw_text"] = (
            df_raw.fillna("").astype(str).agg(" | ".join, axis=1)
        )

        df = df.dropna(subset=["date_booked", "amount"])

        st.dataframe(
            df[["date_booked", "amount", "own_description"]],
            height=280,
            width="stretch"
        )

        if st.button("💾 Gem og kategorisér automatisk"):
            try:
                records = [
                    {
                        "user_id": USER_ID,
                        "date_booked": r.date_booked.isoformat(),
                        "amount": r.amount,
                        "own_description": r.own_description,
                        "orig_description": r.orig_description,
                        "raw_text": r.raw_text,
                    }
                    for r in df.itertuples(index=False)
                ]

                supabase.table("transactions").insert(records).execute()
                supabase.rpc("run_auto_categorization", {}).execute()

                st.success(f"✅ {len(records)} transaktioner importeret")

            except Exception as e:
                st.error(e)
                st.stop()

    st.markdown("</div>", unsafe_allow_html=True)

# =========================================================
# MANUAL CATEGORIZATION
# =========================================================
st.markdown("## 🏷️ Manuel kategorisering")
st.caption("Dit valg prioriteres altid og bruges til at lære nye regler")

txs = (
    supabase
    .table("transactions")
    .select("id, date_booked, amount, orig_description, category_id")
    .eq("user_id", USER_ID)
    .order("date_booked", desc=True)
    .limit(30)
    .execute()
    .data
)

options = ["(Ingen)"] + category_names

for t in txs:
    amount_class = "amount-negative" if t["amount"] < 0 else "amount-positive"
    badge_class = "badge-manual" if t["category_id"] else "badge-auto"
    badge_text = "Manuel" if t["category_id"] else "Ukategoriseret"

    st.markdown(f"""
    <div class="card tx-card">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div>
                <div class="tx-title">{t['orig_description']}</div>
                <div class="tx-date">{t['date_booked']}</div>
                <span class="badge {badge_class}">{badge_text}</span>
            </div>
            <div class="{amount_class}">
                {t['amount']:.2f} kr
            </div>
        </div>
    """, unsafe_allow_html=True)

    current_cat = cat_id_to_name.get(t["category_id"], "(Ingen)")
    current_index = options.index(current_cat) if current_cat in options else 0

    selected = st.selectbox(
        "Kategori",
        options,
        index=current_index,
        key=f"cat_{t['id']}"
    )

    if st.button("💾 Gem kategori", key=f"save_{t['id']}") and selected != "(Ingen)":
        cat_id = cat_name_to_id[selected]

        supabase.table("transactions").update({
            "category_id": cat_id
        }).eq("id", t["id"]).execute()

        supabase.table("category_overrides").insert({
            "transaction_id": t["id"],
            "category_id": cat_id
        }).execute()

        keyword = t["orig_description"].strip().upper()
        exists = (
            supabase
            .table("rules")
            .select("id")
            .eq("keyword", keyword)
            .limit(1)
            .execute()
            .data
        )

        if not exists:
            supabase.table("rules").insert({
                "keyword": keyword,
                "category_id": cat_id,
                "priority": 100
            }).execute()

        st.success("✅ Kategori gemt og systemet har lært mønstret")

    st.markdown("</div>", unsafe_allow_html=True)
