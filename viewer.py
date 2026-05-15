import streamlit as st
import requests

API = "http://127.0.0.1:8000/api/events/chat/"

st.title("K-Dive 이벤트 추천")

if "messages" not in st.session_state:
    st.session_state.messages = []      # 화면 표시용 (events 포함)
if "api_messages" not in st.session_state:
    st.session_state.api_messages = []  # API 전달용 (텍스트만)

# 이전 대화 렌더링
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg.get("content"):
            st.markdown(msg["content"])
        for ev in msg.get("events", []):
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
                    link_url = ev.get("store_url") or ev.get("detail_url", "")
                    st.markdown(f"[팝업스토어 페이지 바로가기]({link_url})")

# 새 입력
if query := st.chat_input("궁금한 이벤트를 물어보세요..."):
    st.session_state.messages.append({"role": "user", "content": query})
    st.session_state.api_messages.append({"role": "user", "content": query})

    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("추천 중..."):
            res = requests.post(
                API,
                json={
                    "query": query,
                    "messages": st.session_state.api_messages[:-1],
                }
            )
            data = res.json()

        message = data.get("message", "")
        events = data.get("events", [])

        if message:
            st.markdown(message)
        elif not events:
            st.markdown("앗, 딱 맞는 이벤트를 못 찾겠어요 😅 다른 조건으로 찾아볼까요?")

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
                    link_url = ev.get("store_url") or ev.get("detail_url", "")
                    st.markdown(f"[팝업스토어 페이지 바로가기]({link_url})")

        st.session_state.api_messages.append({"role": "assistant", "content": message})
        st.session_state.messages.append({
            "role": "assistant",
            "content": message,
            "events": events,
        })
