import streamlit as st
import pandas as pd
from supabase import create_client

# ---------- Streamlit ----------
st.set_page_config(page_title="Privat økonomi", layout="wide")
st.title("💳 Min privatøkonomi")

# ---------- Supabase ----------
supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

# ---------- CSV upload ----------
st.header("1️⃣ Upload CSV fra netbank")

uploaded_file = st.file_uploader("Vælg CSV-fil", type="csv")

if uploaded_file:
    # Læs CSV (din fil har ; og ingen header)
    df_raw = pd.read_csv(
        uploaded_file,
        sep=";",
        header=None,
        dtype=str
    )

    # Udvælg relevante kolonner
    df = pd.DataFrame({
        "orig_description": df_raw[0].fillna(""),
        "amount_raw": df_raw[4],
        "date_raw": df_raw[8]
    })

    # Rens beløb (1.201,44 -> 1201.44)
    df["amount"] = (
        df["amount_raw"]
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .astype(float)
    )

    # Konverter dato
    df["date_booked"] = pd.to_datetime(
        df["date_raw"],
        format="%d-%m-%Y",
        errors="coerce"
    ).dt.date

    # Rå linje (til regler senere)
    df["raw_text"] = df_raw.apply(
        lambda row: " | ".join([x for x in row if pd.notna(x)]),
        axis=1
    )

    # own_description starter som orig_description
    df["own_description"] = df["orig_description"]

    # Endeligt datasæt
    df = df[
        [
            "date_booked",
            "amount",
            "orig_description",
            "own_description",
            "raw_text"
        ]
    ]

    # Fjern rækker hvor dato eller beløb fejler
    df = df.dropna(subset=["date_booked", "amount"])

    st.subheader("📄 Forhåndsvisning")
    st.dataframe(df)

    # ---------- Gem i Supabase ----------
    if st.button("Gem transaktioner"):
        with st.spinner("Gemmer transaktioner..."):
            count = 0

            for _, row in df.iterrows():
                supabase.table("transactions").insert({
                    "date_booked": row["date_booked"].isoformat(),
                    "amount": row["amount"],
                    "orig_description": row["orig_description"],
                    "own_description": row["own_description"],
                    "raw_text": row["raw_text"]
                }).execute()

                count += 1

        st.success(f"✅ {count} transaktioner gemt")

# ---------- Vis eksisterende ----------
st.header("2️⃣ Seneste transaktioner")

res = supabase.table("transactions") \
    .select(
        "date_booked, amount, orig_description, own_description, category_id"
    ) \
    .order("date_booked", desc=True) \
    .limit(50) \
    .execute()

if res.data:
    st.dataframe(pd.DataFrame(res.data))
else:
    st.info("Ingen transaktioner endnu.")
