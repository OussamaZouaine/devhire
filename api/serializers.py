from django.utils import timezone
from rest_framework import serializers

from accounts.models import CandidateProfile, Company, User
from applications.models import Application
from jobs.models import JobOffer
from matching.models import Skill
from messaging.models import Notification


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ("id", "name", "slug")


class SkillNamesField(serializers.ListField):
    """Skills are read and written as a list of names: ["Python", "Django"]."""

    child = serializers.CharField(max_length=60)

    def to_representation(self, value):
        return [skill.name for skill in value.all()]

    def to_internal_value(self, data):
        names = super().to_internal_value(data)
        return [Skill.objects.get_or_create_by_name(name) for name in names if name.strip()]


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ("id", "name", "slug", "logo", "description", "website", "location")


class JobOfferSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    skills = SkillNamesField(required=False)
    contract_type_display = serializers.CharField(source="get_contract_type_display", read_only=True)
    remote_policy_display = serializers.CharField(source="get_remote_policy_display", read_only=True)
    is_open = serializers.BooleanField(read_only=True)

    class Meta:
        model = JobOffer
        fields = (
            "id",
            "title",
            "description",
            "company",
            "location",
            "contract_type",
            "contract_type_display",
            "remote_policy",
            "remote_policy_display",
            "experience_level",
            "skills",
            "salary_min",
            "salary_max",
            "deadline",
            "is_active",
            "is_open",
            "created_at",
        )
        read_only_fields = ("created_at",)

    def validate_deadline(self, value):
        if value and value < timezone.localdate():
            raise serializers.ValidationError("La date limite ne peut pas être dans le passé.")
        return value

    def validate(self, attrs):
        salary_min = attrs.get("salary_min", getattr(self.instance, "salary_min", None))
        salary_max = attrs.get("salary_max", getattr(self.instance, "salary_max", None))
        if salary_min and salary_max and salary_min > salary_max:
            raise serializers.ValidationError({"salary_max": "Doit être supérieur au salaire minimum."})
        return attrs

    def create(self, validated_data):
        skills = validated_data.pop("skills", [])
        offer = super().create(validated_data)
        offer.skills.set(skills)
        return offer

    def update(self, instance, validated_data):
        skills = validated_data.pop("skills", None)
        offer = super().update(instance, validated_data)
        if skills is not None:
            offer.skills.set(skills)
        return offer


class MatchSerializer(serializers.Serializer):
    score = serializers.IntegerField()
    skill_score = serializers.IntegerField()
    text_score = serializers.IntegerField()
    matched_skills = serializers.ListField(child=serializers.CharField())
    missing_skills = serializers.ListField(child=serializers.CharField())


class RecommendationSerializer(serializers.Serializer):
    offer = JobOfferSerializer()
    match = MatchSerializer()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "first_name", "last_name", "email", "role")
        read_only_fields = ("id", "username", "role")


class CandidateProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    skills = SkillNamesField(required=False)
    has_cv = serializers.SerializerMethodField()

    class Meta:
        model = CandidateProfile
        fields = ("id", "user", "headline", "years_of_experience", "phone", "location", "bio", "skills", "has_cv")

    def get_has_cv(self, obj) -> bool:
        return bool(obj.cv)

    def update(self, instance, validated_data):
        skills = validated_data.pop("skills", None)
        instance = super().update(instance, validated_data)
        if skills is not None:
            instance.skills.set(skills)
        return instance


class ApplicationSerializer(serializers.ModelSerializer):
    job_offer = serializers.PrimaryKeyRelatedField(queryset=JobOffer.objects.open())
    job_offer_title = serializers.CharField(source="job_offer.title", read_only=True)
    company = serializers.CharField(source="job_offer.company.name", read_only=True)
    candidate = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Application
        fields = (
            "id",
            "job_offer",
            "job_offer_title",
            "company",
            "candidate",
            "status",
            "status_display",
            "cover_letter",
            "match_score",
            "applied_at",
            "updated_at",
        )
        read_only_fields = ("status", "match_score", "applied_at", "updated_at")

    def get_candidate(self, obj) -> dict:
        user = obj.candidate.user
        return {"id": obj.candidate_id, "name": user.display_name, "email": user.email}


class StatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[(s.value, s.label) for s in Application.PIPELINE])
    note = serializers.CharField(max_length=255, required=False, allow_blank=True)


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ("id", "kind", "title", "body", "url", "is_read", "created_at")
        read_only_fields = fields
