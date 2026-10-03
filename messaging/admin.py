from django.contrib import admin

from .models import Message, Notification


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("application", "sender", "created_at", "read_at")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "kind", "title", "is_read", "created_at")
    list_filter = ("kind", "is_read")
