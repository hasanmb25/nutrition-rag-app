import streamlit as st


@st.cache_resource
def initialize_database():
    import database

    database.init_db()


@st.cache_resource
def load_vector_store():
    import rag_chain

    initialize_database()
    return rag_chain.build_or_load_vector_store()
