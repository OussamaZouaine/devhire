from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CandidateProfile, RecruiterProfile, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "role", "is_staff", "is_active")
    list_filter = ("role", "is_staff", "is_active")
    fieldsets = UserAdmin.fieldsets + (
        ("Rôle DevHire", {"fields": ("role",)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Rôle DevHire", {"fields": ("role",)}),
    )


@admin.register(CandidateProfile)
class CandidateProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "location", "phone")
    search_fields = ("user__username", "user__email", "location")


@admin.register(RecruiterProfile)
class RecruiterProfileAdmin(admin.ModelAdmin):
    list_display = ("company_name", "user", "website")
    search_fields = ("company_name", "user__username")
