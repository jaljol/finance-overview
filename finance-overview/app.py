import streamlit as st
import pandas as pd
from supabase import create_client

# ================================
# Setup
# ================================
st.set_page_config(page_title="Privat økonomi", layout="wide")
st.title("💳 Min privatøkonomi")

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
