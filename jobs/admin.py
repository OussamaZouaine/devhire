from django.contrib import admin

from .models import JobAlert, JobOffer, JobOfferView, SavedJob


@admin.register(JobOffer)
class JobOfferAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "company",
        "location",
        "contract_type",
        "remote_policy",
        "is_active",
        "deadline",
        "created_at",
    )
    list_filter = ("contract_type", "remote_policy", "experience_level", "is_active")
    search_fields = ("title", "description", "company__name")
    filter_horizontal = ("skills",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(SavedJob)
class SavedJobAdmin(admin.ModelAdmin):
    list_display = ("candidate", "job_offer", "created_at")


@admin.register(JobAlert)
class JobAlertAdmin(admin.ModelAdmin):
    list_display = ("name", "candidate", "query", "location", "is_active", "last_sent_at")
    list_filter = ("is_active",)


@admin.register(JobOfferView)
class JobOfferViewAdmin(admin.ModelAdmin):
    list_display = ("job_offer", "user", "viewed_on")
    list_filter = ("viewed_on",)
