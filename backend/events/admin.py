from django.contrib import admin
from events.models import Event

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'new_main_category', 'region', 'location', 'start_date', 'end_date')
    search_fields = ('title', 'location', 'description')
    list_filter = ('new_main_category', 'region')
