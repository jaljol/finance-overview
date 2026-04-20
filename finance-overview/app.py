import streamlit as st
import pandas as pd
from supabase import create_client

# ---------- Streamlit ----------
st.set_page_config(
    page_title="Privat økonomi",
    layout="wide"
)

st.title("💳 Min privatøkonomi")


# ---------- Supabase ----------
supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)


# ---------- CSV upload ----------
st.header("1️⃣ Upload CSV fra netbank")

uploaded_file = st.file_uploader(
    "Vælg CSV-fil",
    type="csv"
)

if uploaded_file:
    # 1) Læs CSV: ; som separator, ingen header
    df_raw = pd.read_csv(
        uploaded_file,
        sep=";",
        header=None,
        dtype=str
    )

    # 2) Map CSV-kolonner til DB-struktur
    df = pd.DataFrame({
        # ✅ som ønsket:
        "own_description": df_raw[0].fillna(""),
        "orig_description": df_raw[1].fillna(""),

        # beløb og dato
        "amount_raw": df_raw[4],
        "date_raw": df_raw[8],
    })

    # 3) Rens beløb (fx 1.201,44 → 1201.44)
    df["amount"] = (
        df["amount_raw"]
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .astype(float)
    )

    # 4) Konverter dato (dd-mm-yyyy)
    df["date_booked"] = pd.to_datetime(
        df["date_raw"],
        format="%d-%m-%Y",
        errors="coerce"
    ).dt.date

    # 5) Saml hele CSV-rækken som raw_text (ROBUST LØSNING)
    df["raw_text"] = df_raw.apply(
        lambda row: " | ".join(
            [x for x in row if pd.notna(x)]
        ),
        axis=1
    )

    # 6) Behold kun kolonner, der passer til DB
    df = df[
        [
            "date_booked",
            "amount",
            "own_description",
            "orig_description",
            "raw_text",
        ]
    ]

    # 7) Fjern rækker der ikke kan gemmes (NOT NULL-felter)
    df = df.dropna(subset=["date_booked", "amount"])


    # ---------- Preview ----------
    st.subheader("📄 Forhåndsvisning")
    st.dataframe(df, use_container_width=True)


    # ---------- Gem i Supabase ----------
    if st.button("💾 Gem transaktioner"):
        with st.spinner("Gemmer transaktioner i databasen..."):
            count = 0

            for _, row in df.iterrows():
                supabase.table("transactions").insert({
                    "date_booked": row["date_booked"].isoformat(),
                    "amount": row["amount"],
                    "own_description": row["own_description"],
                    "orig_description": row["orig_description"],
                    "raw_text": row["raw_text"],
                }).execute()

                count += 1

        st.success(f"✅ {count} transaktioner gemt")


# ---------- Vis gemte transaktioner ----------
st.header("2️⃣ Seneste transaktioner")

res = (
    supabase
    .table("transactions")
    .select(
        "date_booked, amount, own_description, orig_description, category_id"
    )
    .order("date_booked", desc=True)
    .limit(50)
    .execute()
)

if res.data:
    st.dataframe(
        pd.DataFrame(res.data),
        use_container_width=True
    )
else:
    st.info("Ingen transaktioner gemt endnu.")
