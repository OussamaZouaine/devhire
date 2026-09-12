from django.contrib import admin

from .models import JobOffer


@admin.register(JobOffer)
class JobOfferAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "recruiter",
        "location",
        "contract_type",
        "is_active",
        "created_at",
    )
    list_filter = ("contract_type", "is_active", "location")
    search_fields = ("title", "keywords", "description")
    readonly_fields = ("created_at", "updated_at")
