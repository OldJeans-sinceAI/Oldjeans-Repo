import json

import streamlit as st

import core
import render

st.set_page_config(page_title="Näkyvyystesti", page_icon="🔎", layout="centered")
st.markdown(f"<style>{render.CSS}.block-container{{padding-top:2rem}}</style>", unsafe_allow_html=True)

st.title("Löytyykö yrityksesi verkosta?")
st.write("Testi tarkistaa, näkyykö yritys Googlessa, Fonectassa, sosiaalisessa mediassa ja hakemistoissa, ja onko oma verkkosivusto kunnossa.")

with st.form("test"):
    company = st.text_input("Yrityksen nimi", placeholder="Esimerkki Oy")
    c1, c2 = st.columns(2)
    city = c1.text_input("Paikkakunta", placeholder="Helsinki")
    phone = c2.text_input("Puhelinnumero (valinnainen)", placeholder="040 123 4567")
    site = st.text_input("Verkkosivusto (valinnainen)", placeholder="www.esimerkki.fi")
    go = st.form_submit_button("Testaa näkyvyys", type="primary", use_container_width=True)

if go:
    if not company.strip() or not city.strip():
        st.error("Anna yrityksen nimi ja paikkakunta.")
    else:
        bar = st.progress(0.0, text="Aloitetaan...")
        try:
            st.session_state["result"] = core.run_test(
                company.strip(), city.strip(), site, phone, lambda f, m: bar.progress(f, text=m))
        except Exception as exc:
            st.session_state.pop("result", None)
            st.error(f"Testi epäonnistui: {exc}")
            st.info("Hakupalvelu voi rajoittaa pyyntöjä. Yritä uudelleen hetken kuluttua.")
        bar.empty()

r = st.session_state.get("result")
if r:
    st.markdown(render.body(r), unsafe_allow_html=True)
    st.write("")
    d1, d2 = st.columns(2)
    d1.download_button("Lataa raportti (HTML)", render.report_html(r), "nakyvyysraportti.html", "text/html", use_container_width=True)
    d2.download_button("Lataa data (JSON)", json.dumps(r, ensure_ascii=False, indent=2), "nakyvyysraportti.json",
                       "application/json", use_container_width=True)
