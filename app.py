import streamlit as st
from pack import AlphexPack

st.set_page_config(page_title="Alphex AI V2 MO")
st.title("Alphex AI V2 MO")
st.caption("A wolf-pack AI: Beta guards, Alpha leads, Gamma specializes, Omega keeps the peace.")

if "pack" not in st.session_state:
    st.session_state.pack = AlphexPack(api_key=st.secrets["GROQ_API_KEY"])
if "history" not in st.session_state:
    st.session_state.history = []

for role, msg in st.session_state.history:
    st.chat_message(role).write(msg)

question = st.chat_input("Ask the pack...")
if question:
    st.chat_message("user").write(question)
    st.session_state.history.append(("user", question))
    with st.spinner("The pack is hunting..."):
        try:
            answer, log = st.session_state.pack.run(question)
        except Exception as error:
            answer, log = ("The pack is resting (free limit reached or network issue). "
                           "Please try again in a minute."), [str(error)]
    st.chat_message("assistant").write(answer)
    with st.expander("Show pack activity"):
        for line in log:
            st.write("• " + line)
    st.session_state.history.append(("assistant", answer))
