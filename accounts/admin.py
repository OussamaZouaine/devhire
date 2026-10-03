from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    CandidateProfile,
    Company,
    CompanyInvitation,
    Education,
    Experience,
    Language,
    RecruiterProfile,
    User,
)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "role", "is_staff", "is_active")
    list_filter = ("role", "is_staff", "is_active")
    fieldsets = UserAdmin.fieldsets + (("Rôle DevHire", {"fields": ("role",)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Rôle DevHire", {"fields": ("role",)}),)


class ExperienceInline(admin.TabularInline):
    model = Experience
    extra = 0


class EducationInline(admin.TabularInline):
    model = Education
    extra = 0


class LanguageInline(admin.TabularInline):
    model = Language
    extra = 0


@admin.register(CandidateProfile)
class CandidateProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "headline", "location", "phone")
    search_fields = ("user__username", "user__email", "location", "headline")
    filter_horizontal = ("skills",)
    inlines = [ExperienceInline, EducationInline, LanguageInline]


class RecruiterInline(admin.TabularInline):
    model = RecruiterProfile
    extra = 0
    fields = ("user", "company_role", "job_title")


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "location", "website", "created_at")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    inlines = [RecruiterInline]


@admin.register(RecruiterProfile)
class RecruiterProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "company", "company_role", "job_title")
    list_filter = ("company_role",)
    search_fields = ("company__name", "user__username")


@admin.register(CompanyInvitation)
class CompanyInvitationAdmin(admin.ModelAdmin):
    list_display = ("email", "company", "role", "created_at", "accepted_at")
    search_fields = ("email", "company__name")
