import streamlit as st
import database
import rag_chain
from app_services import initialize_database

initialize_database()

st.header("Your Daily Nutrition Dashboard")

totals = database.get_today_totals()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Calories", f"{totals['calories']} kcal")
col2.metric("Protein", f"{totals['protein']} g")
col3.metric("Carbs", f"{totals['carbs']} g")
col4.metric("Fat", f"{totals['fat']} g")

st.divider()

st.subheader("Generate Clinical Critique")
st.write("Get professional feedback from the AI (gpt-4o) based on your logged intake today.")

if st.button("Synthesize Health Report", type="primary"):
    with st.spinner("Consulting Clinical AI..."):
        critique_chain = rag_chain.get_clinical_critique_chain()

        report = critique_chain.invoke(
            {
                "calories": totals["calories"],
                "protein": totals["protein"],
                "carbs": totals["carbs"],
                "fat": totals["fat"],
            }
        )

        st.info(report)
