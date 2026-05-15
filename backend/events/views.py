from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from events import agent


@api_view(['POST'])
def event_search(request):
    """
    1단계 테스트용 — LLM 없이 DB 검색 결과만 반환
    POST /api/events/search/
    Body: { "query": "...", "mood": "..." }
    """
    query = request.data.get('query', '').strip()
    if not query:
        return Response({'error': 'query 필드가 필요합니다.'}, status=status.HTTP_400_BAD_REQUEST)

    mood = request.data.get('mood', '')
    events = agent.search_events(query=query, mood=mood)

    results = [
        {
            'title': ev.title,
            'location': ev.location,
            'date': f"{ev.start_date} ~ {ev.end_date}" if ev.start_date else '',
            'thumbnail_url': ev.thumbnail_url,
            'detail_url': ev.detail_url,
            'store_url': ev.store_url,
        }
        for ev in events
    ]

    return Response({'count': len(results), 'events': results})


@api_view(['POST'])
def event_chat(request):
    """
    대화형 추천 — 대화 기록을 받아 맥락을 유지하며 추천
    POST /api/events/chat/
    Body: { "query": "...", "messages": [{"role": "user/assistant", "content": "..."}] }
    """
    query = request.data.get('query', '').strip()
    if not query:
        return Response({'error': 'query 필드가 필요합니다.'}, status=status.HTTP_400_BAD_REQUEST)

    messages = request.data.get('messages', [])
    result = agent.chat(messages=messages, query=query)
    return Response(result)


@api_view(['POST'])
def event_recommend(request):
    """
    2단계 — LLM 큐레이션 포함 (ANTHROPIC_API_KEY 필요)
    POST /api/events/recommend/
    Body: { "query": "...", "genres": [...], "artists": [...], "mood": "..." }
    """
    query = request.data.get('query', '').strip()
    if not query:
        return Response({'error': 'query 필드가 필요합니다.'}, status=status.HTTP_400_BAD_REQUEST)

    results = agent.run(
        query=query,
        genres=request.data.get('genres', []),
        artists=request.data.get('artists', []),
        mood=request.data.get('mood', ''),
    )

    return Response({'events': results})
