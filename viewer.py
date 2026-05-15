import streamlit as st
import requests

API = "http://127.0.0.1:8000/api/events"

st.title("팝업스토어 뷰어")

query = st.text_input("검색어", value="성수 팝업")
mode = st.radio("모드", ["search (DB만)", "recommend (LLM 큐레이션)"], horizontal=True)

if st.button("검색"):
    endpoint = f"{API}/search/" if mode.startswith("search") else f"{API}/recommend/"
    res = requests.post(endpoint, json={"query": query, "mood": ""})
    data = res.json()
    events = data.get("events", [])
    st.write(f"**{len(events)}개 결과**")

    for ev in events:
        with st.container(border=True):
            col1, col2 = st.columns([1, 3])
            with col1:
                url = ev.get("thumbnail_url", "")
                if url.startswith("/"):
                    url = "https://dayforyou.com" + url
                if url:
                    st.image(url, width=150)
            with col2:
                st.markdown(f"### {ev['title']}")
                st.write(f"📍 {ev.get('location', '')}")
                st.write(f"📅 {ev.get('date', '')}")
                if ev.get("reason"):
                    st.info(ev["reason"])
                if ev.get("hashtags"):
                    st.write(" ".join(ev["hashtags"][:5]))
                link_url = ev.get("store_url") or ev.get("detail_url", "")
                st.markdown(f"[팝업스토어 페이지 바로가기]({link_url})")
