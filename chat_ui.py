"""
K-Dive 이벤트 에이전트 채팅 UI
실행: streamlit run chat_ui.py
"""

import streamlit as st
import requests

API_URL = "http://localhost:8000/api/events/chat/"

st.set_page_config(page_title="K-Dive 이벤트 추천", page_icon="🎵", layout="wide")

# 자동완성·자동수정 비활성화 (한국어 IME 오작동 방지)
st.markdown("""
<script>
(function disableAutocorrect() {
    function patch(root) {
        root.querySelectorAll('textarea, input[type="text"], input:not([type])').forEach(el => {
            el.setAttribute('autocorrect', 'off');
            el.setAttribute('autocomplete', 'off');
            el.setAttribute('spellcheck', 'false');
        });
    }
    patch(document);
    new MutationObserver(m => m.forEach(r => r.addedNodes.forEach(n => {
        if (n.nodeType === 1) patch(n);
    }))).observe(document.body, { childList: true, subtree: true });
})();
</script>
""", unsafe_allow_html=True)

col_title, col_btn = st.columns([5, 1])
with col_title:
    st.title("🎵 K-Dive 이벤트 추천 에이전트")
    st.caption("콘서트, 팝업스토어, 페스티벌 등 원하는 이벤트를 자유롭게 물어보세요!")
with col_btn:
    st.write("")
    st.write("")
    if st.button("🗑️ 대화 초기화"):
        st.session_state.messages = []
        st.rerun()

if "messages" not in st.session_state:
    st.session_state.messages = []

# 대화 기록 출력
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("events"):
            for ev in msg["events"]:
                with st.expander(f"📍 {ev.get('title', '')} — {ev.get('location', '')}"):
                    col1, col2 = st.columns([1, 3])
                    with col1:
                        if ev.get("thumbnail_url"):
                            st.image(ev["thumbnail_url"], width=150)
                    with col2:
                        st.markdown(f"**날짜**: {ev.get('date', '-')}")
                        st.markdown(f"**장소**: {ev.get('location', '-')}")
                        if ev.get("reason"):
                            st.markdown(f"**추천 이유**: {ev.get('reason')}")
                        if ev.get("detail_url"):
                            st.markdown(f"[🔗 상세 보기]({ev['detail_url']})")

# 입력창
if user_input := st.chat_input("예: 홍대 힙합 콘서트 추천해줘, 성수 팝업스토어 알려줘"):
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # API에 대화 기록도 같이 보내기 (다중 턴 맥락 유지)
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages[:-1]  # 방금 추가한 것 제외
    ]

    with st.chat_message("assistant"):
        with st.spinner("검색 중..."):
            try:
                resp = requests.post(
                    API_URL,
                    json={"query": user_input, "messages": history},
                    headers={"Content-Type": "application/json"},
                    timeout=60,
                )
                data = resp.json()

                reply = data.get("reply") or data.get("message") or "응답을 받지 못했어요."
                events = data.get("events", [])

                st.markdown(reply)

                for ev in events:
                    with st.expander(f"📍 {ev.get('title', '')} — {ev.get('location', '')}"):
                        col1, col2 = st.columns([1, 3])
                        with col1:
                            if ev.get("thumbnail_url"):
                                st.image(ev["thumbnail_url"], width=150)
                        with col2:
                            st.markdown(f"**날짜**: {ev.get('date', '-')}")
                            st.markdown(f"**장소**: {ev.get('location', '-')}")
                            if ev.get("reason"):
                                st.markdown(f"**추천 이유**: {ev.get('reason')}")
                            if ev.get("detail_url"):
                                st.markdown(f"[🔗 상세 보기]({ev['detail_url']})")

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": reply,
                    "events": events,
                })

            except requests.exceptions.ConnectionError:
                st.error("Django 서버에 연결할 수 없습니다. `python manage.py runserver` 실행 여부를 확인하세요.")
            except Exception as e:
                st.error(f"오류 발생: {e}")
