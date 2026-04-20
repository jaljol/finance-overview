import streamlit as st
import pandas as pd
from supabase import create_client

# ================================
# Streamlit setup
# ================================
st.set_page_config(
    page_title="Privat økonomi",
    layout="wide"
)
st.title("💳 Min privatøkonomi")

# ================================
# Supabase
# ================================
supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"],
)

USER_ID = "janus"  # bruges til RLS


# ================================
# CSV Upload
# ================================
st.header("1️⃣ Upload CSV fra netbank")

uploaded_file = st.file_uploader("Vælg CSV-fil", type="csv")

if uploaded_file:
    # --- Læs CSV (din fil: ; og ingen header) ---
    df_raw = pd.read_csv(
        uploaded_file,
        sep=";",
        header=None,
        dtype=str,
    )

    # --- Map kolonner ---
    df = pd.DataFrame({
        "own_description": df_raw[0].fillna(""),
        "orig_description": df_raw[1].fillna(""),
        "amount_raw": df_raw[4],
        "date_raw": df_raw[8],
    })

    # --- Rens beløb ---
    df["amount"] = (
        df["amount_raw"]
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .astype(float)
    )

    # --- Konverter dato ---
    df["date_booked"] = pd.to_datetime(
        df["date_raw"],
        format="%d-%m-%Y",
        errors="coerce"
    ).dt.date

    # --- raw_text (hurtig og robust) ---
    df["raw_text"] = (
        df_raw
        .fillna("")
        .astype(str)
        .agg(" | ".join, axis=1)
    )

    # --- Slutdatasæt ---
    df = df[
        [
            "date_booked",
            "amount",
            "own_description",
            "orig_description",
            "raw_text",
        ]
    ]

    # Fjern ugyldige rækker
    df = df.dropna(subset=["date_booked", "amount"])

    # ================================
    # Preview
    # ================================
    st.subheader("📄 Forhåndsvisning")
    st.dataframe(df, width="stretch")

    # ================================
    # Batch insert
    # ================================
    if st.button("💾 Gem transaktioner"):
        with st.spinner("Gemmer transaktioner..."):
            records = [
                {
                    "date_booked": row.date_booked.isoformat(),
                    "amount": row.amount,
                    "own_description": row.own_description,
                    "orig_description": row.orig_description,
                    "raw_text": row.raw_text,
                    "user_id": USER_ID,
                }
                for row in df.itertuples(index=False)
            ]

            result = supabase.table("transactions").insert(records).execute()

            if result.error:
                st.error(result.error)
                st.stop()

        st.success(f"✅ {len(records)} transaktioner gemt")

        # --- Kør auto-kategorisering automatisk ---
        supabase.rpc("run_auto_categorization", {}).execute()
        st.info("⚡ Automatisk kategorisering kørt")


# ================================
# Manuel auto-kategorisering
# ================================
st.header("⚡ Automatisk kategorisering")

if st.button("Kør auto-kategorisering igen"):
    with st.spinner("Anvender regler..."):
        result = supabase.rpc("run_auto_categorization", {}).execute()
        if result.error:
            st.error(result.error)
            st.stop()
    st.success("✅ Kategorisering færdig")


# ================================
# Vis seneste transaktioner
# ================================
st.header("2️⃣ Seneste transaktioner")

res = (
    supabase
    .table("transactions")
    .select(
        "date_booked, amount, own_description, orig_description, category_id"
    )
    .eq("user_id", USER_ID)
    .order("date_booked", desc=True)
    .limit(50)
    .execute()
)

if res.data:
    st.dataframe(
        pd.DataFrame(res.data),
        width="stretch"
    )
else:
    st.info("Ingen transaktioner gemt endnu.")
