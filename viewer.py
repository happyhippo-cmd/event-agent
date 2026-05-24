import streamlit as st
import requests

API = "http://127.0.0.1:8000/api/events/chat/"

st.title("K-Dive 이벤트 추천")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "api_messages" not in st.session_state:
    st.session_state.api_messages = []
if "pending_query" not in st.session_state:
    st.session_state.pending_query = None


def send_query(query: str):
    st.session_state.pending_query = query


def category_query(cat: str, category_type: str, location: str = "") -> str:
    keyword = cat.replace("/", " ")  # "아트/회화" → "아트 회화"
    loc = f"{location} " if location and location != "서울" else (f"{location} " if location else "")
    if category_type == "exhibition":
        return f"{loc}{keyword} 전시 추천해줘"
    return f"{loc}{keyword} 팝업 추천해줘"


def render_event_card(ev):
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
            st.markdown(f"[페이지 바로가기]({link_url})")


def render_categories(categories, category_type, key_prefix, location=""):
    cols = st.columns(len(categories))
    for i, cat in enumerate(categories):
        if cols[i].button(cat, key=f"{key_prefix}_{i}"):
            send_query(category_query(cat, category_type, location))


# 이전 대화 렌더링
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg.get("content"):
            st.markdown(msg["content"])
        for ev in msg.get("events", []):
            render_event_card(ev)
        if msg.get("categories"):
            render_categories(msg["categories"], msg.get("category_type", "popup"), f"cat_{id(msg)}", msg.get("location", ""))

# pending_query 처리 (카테고리 버튼 클릭)
if st.session_state.pending_query:
    query = st.session_state.pending_query
    st.session_state.pending_query = None
    st.session_state.messages.append({"role": "user", "content": query})
    st.session_state.api_messages.append({"role": "user", "content": query})

    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("추천 중..."):
            res = requests.post(API, json={"query": query, "messages": st.session_state.api_messages[:-1]})
            data = res.json()

        message = data.get("message", "")
        events = data.get("events", [])
        categories = data.get("categories", [])
        category_type = data.get("category_type", "popup")
        location = data.get("location", "")

        if message:
            st.markdown(message)
        for ev in events:
            render_event_card(ev)
        if categories:
            render_categories(categories, category_type, "pending_cat", location)

        st.session_state.api_messages.append({"role": "assistant", "content": message})
        st.session_state.messages.append({
            "role": "assistant", "content": message,
            "events": events, "categories": categories, "category_type": category_type, "location": location,
        })
    st.rerun()

# 새 입력
if query := st.chat_input("궁금한 이벤트를 물어보세요..."):
    st.session_state.messages.append({"role": "user", "content": query})
    st.session_state.api_messages.append({"role": "user", "content": query})

    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("추천 중..."):
            res = requests.post(API, json={"query": query, "messages": st.session_state.api_messages[:-1]})
            data = res.json()

        message = data.get("message", "")
        events = data.get("events", [])
        categories = data.get("categories", [])
        category_type = data.get("category_type", "popup")
        location = data.get("location", "")

        if message:
            st.markdown(message)
        elif not events and not categories:
            st.markdown("딱 맞는 이벤트를 못 찾겠어 😅 다른 조건으로 찾아볼까?")

        for ev in events:
            render_event_card(ev)
        if categories:
            render_categories(categories, category_type, "input_cat", location)

        st.session_state.api_messages.append({"role": "assistant", "content": message})
        st.session_state.messages.append({
            "role": "assistant", "content": message,
            "events": events, "categories": categories, "category_type": category_type, "location": location,
        })
