from django.contrib import admin

from .models import Application, ApplicationStatusHistory, Interview, RecruiterNote


class StatusHistoryInline(admin.TabularInline):
    model = ApplicationStatusHistory
    extra = 0
    readonly_fields = ("from_status", "to_status", "changed_by", "changed_at", "note")


class RecruiterNoteInline(admin.TabularInline):
    model = RecruiterNote
    extra = 0


class InterviewInline(admin.TabularInline):
    model = Interview
    extra = 0


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("candidate", "job_offer", "status", "match_score", "applied_at")
    list_filter = ("status", "applied_at")
    search_fields = (
        "candidate__user__username",
        "job_offer__title",
    )
    readonly_fields = ("applied_at", "updated_at")
    inlines = [StatusHistoryInline, InterviewInline, RecruiterNoteInline]


@admin.register(Interview)
class InterviewAdmin(admin.ModelAdmin):
    list_display = ("application", "scheduled_at", "mode")
    list_filter = ("mode",)
