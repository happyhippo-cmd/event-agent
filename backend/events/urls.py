from django.urls import path
from events import views

urlpatterns = [
    path('search/', views.event_search),       # 1단계: DB 검색만
    path('recommend/', views.event_recommend), # 2단계: LLM 큐레이션 포함
]
