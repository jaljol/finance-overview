import streamlit as st
import pandas as pd
from supabase import create_client

# ================================
# Setup
# ================================
st.set_page_config(page_title="Privat økonomi", layout="wide")
st.markdown("""
<style>
/* Generel fonte & spacing */
html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
                 Roboto, Oxygen, Ubuntu, Cantarell, "Helvetica Neue", sans-serif;
}

/* Titler */
h1 {
    font-size: 2.2rem;
    margin-bottom: 0.5rem;
}
h2 {
    margin-top: 2.5rem;
}

/* Kort-look */
.card {
    background-color: #ffffff;
    border-radius: 16px;
    padding: 1.2rem 1.4rem;
    box-shadow: 0 8px 20px rgba(0,0,0,0.06);
}

/* Beløb */
.amount-positive {
    color: #16a34a;
    font-weight: 600;
}
.amount-negative {
    color: #dc2626;
    font-weight: 600;
}

/* Badge */
.badge {
    display: inline-block;
    padding: 0.2rem 0.6rem;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
    background-color: #e5e7eb;
}
.badge-auto {
    background-color: #dbeafe;
    color: #1d4ed8;
}
.badge-manual {
    background-color: #dcfce7;
    color: #166534;
}
</style>
""", unsafe_allow_html=True)


st.title("💳 Min privatøkonomi")
st.caption("Privat overblik over dine transaktioner · Automatisk & manuelt kategoriseret")

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

USER_ID = "janus"

# ================================
# Hent kategorier
# ================================
categories = supabase.table("categories") \
    .select("id, name") \
    .eq("is_active", True) \
    .execute().data

cat_name_to_id = {c["name"]: c["id"] for c in categories}
cat_id_to_name = {c["id"]: c["name"] for c in categories}



col1, col2, col3 = st.columns(3)

with col1:
    st.markdown('<div class="card">💰 <b>Saldo (30 dage)</b><br>12.345 kr</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="card">📊 <b>Udgifter</b><br>−4.321 kr</div>', unsafe_allow_html=True)

with col3:
    st.markdown('<div class="card">🏷️ <b>Kategoriseret</b><br>87 %</div>', unsafe_allow_html=True)

# ================================
# CSV Upload
# ================================
st.header("1️⃣ Upload CSV")

file = st.file_uploader("CSV fra netbank", type="csv")

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

    st.dataframe(df[["date_booked", "amount", "own_description"]], width="stretch")

    if st.button("💾 Gem transaktioner"):
        try:
            records = [{
                "user_id": USER_ID,
                "date_booked": r.date_booked.isoformat(),
                "amount": r.amount,
                "own_description": r.own_description,
                "orig_description": r.orig_description,
                "raw_text": r.raw_text,
            } for r in df.itertuples(index=False)]

            supabase.table("transactions").insert(records).execute()
            supabase.rpc("run_auto_categorization", {}).execute()

            st.success(f"✅ {len(records)} transaktioner gemt og kategoriseret")

        except Exception as e:
            st.error(e)
            st.stop()


# ================================
# Manuel kategorisering
# ================================
st.header("2️⃣ Manuel kategorisering")

txs = supabase.table("transactions") \
    .select("id, date_booked, amount, orig_description, category_id") \
    .eq("user_id", USER_ID) \
    .order("date_booked", desc=True) \
    .limit(30) \
    .execute().data

for t in txs:
    with st.expander(f"{t['date_booked']} | {t['amount']} kr | {t['orig_description']}"):

        current_cat = cat_id_to_name.get(t["category_id"], "(Ingen)")
        selected = st.selectbox(
            "Kategori",
            ["(Ingen)"] + list(cat_name_to_id.keys()),
            index=(list(cat_name_to_id.keys()).index(current_cat) + 1)
            if current_cat in cat_name_to_id else 0,
            key=f"cat_{t['id']}"
        )

        if st.button("Gem kategori", key=f"save_{t['id']}") and selected != "(Ingen)":
            cat_id = cat_name_to_id[selected]

            # Opdater transaction
            supabase.table("transactions").update({
                "category_id": cat_id
            }).eq("id", t["id"]).execute()

            # Log override
            supabase.table("category_overrides").insert({
                "transaction_id": t["id"],
                "category_id": cat_id
            }).execute()

            # Lær regel
            keyword = t["orig_description"].strip().upper()

            exists = supabase.table("rules") \
                .select("id") \
                .eq("keyword", keyword) \
                .limit(1) \
                .execute().data

            if not exists:
                supabase.table("rules").insert({
                    "keyword": keyword,
                    "category_id": cat_id,
                    "priority": 100
                }).execute()

            st.success("✅ Kategori gemt og regel lært")
