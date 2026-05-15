from django.db import models


class Event(models.Model):
    CATEGORY_POPUP = 'popup'
    CATEGORY_CHOICES = [
        (CATEGORY_POPUP, '팝업스토어'),
        ('exhibition', '전시'),
        ('festival', '페스티벌/공연'),
        ('fair', '박람회'),
        ('other', '기타'),
    ]

    title = models.CharField(max_length=300)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default=CATEGORY_POPUP)
    location = models.CharField(max_length=500, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)
    thumbnail_url = models.URLField(max_length=1000, blank=True)
    detail_url = models.URLField(max_length=1000, blank=True)
    hashtags = models.JSONField(default=list)
    main_category = models.CharField(max_length=100, blank=True)
    sub_category = models.CharField(max_length=100, blank=True)
    detail_category = models.CharField(max_length=100, blank=True)
    music_genre = models.JSONField(default=list)
    mood_tags = models.JSONField(default=list)
    activity_tags = models.JSONField(default=list)
    theme_tags = models.JSONField(default=list)
    space_tags = models.JSONField(default=list)
    emotion_tags = models.JSONField(default=list)
    audience_tags = models.JSONField(default=list)
    vector_summary = models.TextField(blank=True)
    region = models.CharField(max_length=100, blank=True)
    new_main_category = models.CharField(max_length=100, blank=True)
    new_sub_category = models.CharField(max_length=100, blank=True)
    exhibition_type = models.CharField(max_length=100, blank=True)
    commerciality = models.CharField(max_length=100, blank=True)
    new_mood_tags = models.JSONField(default=list)
    new_audience_tags = models.JSONField(default=list)
    vector_summary_v2 = models.TextField(blank=True)
    store_url = models.URLField(max_length=1000, blank=True)
    source = models.CharField(max_length=100, default='dayforyou')
    source_id = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('source', 'source_id')
        indexes = [
            models.Index(fields=['start_date', 'end_date']),
            models.Index(fields=['category']),
        ]

    def __str__(self):
        return f"[{self.category}] {self.title}"

    @property
    def is_active(self):
        from django.utils import timezone
        today = timezone.localdate()
        if self.end_date and self.end_date < today:
            return False
        return True
