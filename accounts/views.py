from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, FormView, TemplateView, UpdateView

from core.tasks import send_email_task
from jobs.models import JobOffer
from matching.cv_parser import detect_skills
from matching.models import Skill
from messaging.models import Notification
from messaging.services import notify

from .adapters import SIGNUP_ROLE_SESSION_KEY
from .forms import (
    CandidateProfileForm,
    CandidateSignUpForm,
    CompanyForm,
    CompanyInvitationForm,
    EducationFormSet,
    ExperienceFormSet,
    LanguageFormSet,
    RecruiterAccountForm,
    RecruiterSignUpForm,
)
from .mixins import CandidateRequiredMixin, CompanyAdminRequiredMixin, RecruiterRequiredMixin
from .models import CandidateProfile, Company, CompanyInvitation, RecruiterProfile, User
from .tasks import extract_cv_text

AUTH_BACKEND = "django.contrib.auth.backends.ModelBackend"


def dashboard_url_for(user) -> str:
    if user.is_authenticated and user.role == User.Role.RECRUITER:
        return reverse("jobs:recruiter_dashboard")
    return reverse("core:candidate_dashboard")


class SignUpChoiceView(TemplateView):
    template_name = "accounts/signup_choice.html"


class CandidateSignUpView(CreateView):
    form_class = CandidateSignUpForm
    template_name = "accounts/signup_candidate.html"

    def form_valid(self, form):
        user = form.save()
        login(self.request, user, backend=AUTH_BACKEND)
        messages.success(self.request, "Bienvenue ! Complétez votre profil pour obtenir des recommandations.")
        return redirect("accounts:candidate_profile_update")


class RecruiterSignUpView(CreateView):
    form_class = RecruiterSignUpForm
    template_name = "accounts/signup_recruiter.html"

    def form_valid(self, form):
        user = form.save()
        login(self.request, user, backend=AUTH_BACKEND)
        messages.success(self.request, "Bienvenue ! Votre espace recruteur est prêt.")
        return redirect("jobs:recruiter_dashboard")


class GoogleSignUpView(View):
    """Remember the chosen role, then start the Google OAuth flow."""

    def get(self, request, role):
        if role not in User.Role.values or not settings.GOOGLE_CLIENT_ID:
            raise Http404
        if request.user.is_authenticated:
            return redirect(dashboard_url_for(request.user))
        request.session[SIGNUP_ROLE_SESSION_KEY] = role
        return redirect(f"{reverse('google_login')}?process=login")


class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"

    def get_success_url(self) -> str:
        redirect_to = self.get_redirect_url()
        return redirect_to or dashboard_url_for(self.request.user)


class LogoutView(auth_views.LogoutView):
    next_page = reverse_lazy("core:home")


# ---------------------------------------------------------------- candidate


class CandidateProfileUpdateView(CandidateRequiredMixin, UpdateView):
    model = CandidateProfile
    form_class = CandidateProfileForm
    template_name = "accounts/candidate_profile_form.html"
    success_url = reverse_lazy("accounts:candidate_profile_update")

    def get_object(self, queryset=None):
        return self.request.user.get_candidate_profile()

    def form_valid(self, form):
        cv_changed = "cv" in form.changed_data
        response = super().form_valid(form)
        if cv_changed:
            if self.object.cv:
                profile_id = self.object.pk
                transaction.on_commit(lambda: extract_cv_text.delay(profile_id))
            else:
                CandidateProfile.objects.filter(pk=self.object.pk).update(cv_text="")
        messages.success(self.request, "Votre profil a été mis à jour avec succès.")
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = self.object
        known = Skill.objects.values_list("name", flat=True)
        current = {name.lower() for name in profile.skill_names}
        context["suggested_skills"] = [
            name for name in detect_skills(profile.cv_text, known) if name.lower() not in current
        ]
        context["all_skills"] = Skill.objects.all()[:300]
        return context


class AddSuggestedSkillsView(CandidateRequiredMixin, View):
    def post(self, request):
        profile = request.user.get_candidate_profile()
        names = request.POST.getlist("skills")
        allowed = {
            name.lower() for name in detect_skills(profile.cv_text, Skill.objects.values_list("name", flat=True))
        }
        added = 0
        for name in names:
            if name.lower() in allowed:
                profile.skills.add(Skill.objects.get_or_create_by_name(name))
                added += 1
        if added:
            messages.success(request, f"{added} compétence(s) ajoutée(s) depuis votre CV.")
        return redirect("accounts:candidate_profile_update")


class CandidateBackgroundView(CandidateRequiredMixin, TemplateView):
    """Edit experiences, education and languages with inline formsets."""

    template_name = "accounts/candidate_background.html"
    formset_classes = {
        "experience_formset": (ExperienceFormSet, "experiences"),
        "education_formset": (EducationFormSet, "educations"),
        "language_formset": (LanguageFormSet, "languages"),
    }

    def get_formsets(self, data=None):
        profile = self.request.user.get_candidate_profile()
        return {
            name: formset_class(data, instance=profile, prefix=prefix)
            for name, (formset_class, prefix) in self.formset_classes.items()
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(kwargs.get("formsets") or self.get_formsets())
        return context

    def post(self, request):
        formsets = self.get_formsets(request.POST)
        if all(formset.is_valid() for formset in formsets.values()):
            with transaction.atomic():
                for formset in formsets.values():
                    formset.save()
            messages.success(request, "Votre parcours a été enregistré.")
            return redirect("accounts:candidate_background")
        messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
        return self.render_to_response(self.get_context_data(formsets=formsets))


class CandidatePublicProfileView(RecruiterRequiredMixin, DetailView):
    """Candidate profile as seen by recruiters."""

    model = CandidateProfile
    template_name = "accounts/candidate_public_profile.html"
    context_object_name = "profile"

    def get_queryset(self):
        return CandidateProfile.objects.select_related("user").prefetch_related(
            "skills", "experiences", "educations", "languages"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["company_applications"] = self.object.applications.filter(
            job_offer__company=self.get_company()
        ).select_related("job_offer")
        return context


# ---------------------------------------------------------------- recruiter / company


class RecruiterAccountView(RecruiterRequiredMixin, UpdateView):
    form_class = RecruiterAccountForm
    template_name = "accounts/recruiter_account.html"
    success_url = reverse_lazy("accounts:recruiter_account")

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, "Votre compte a été mis à jour.")
        return super().form_valid(form)


class CompanyUpdateView(CompanyAdminRequiredMixin, UpdateView):
    form_class = CompanyForm
    template_name = "accounts/company_form.html"
    success_url = reverse_lazy("accounts:company_update")

    def get_object(self, queryset=None):
        return self.get_company()

    def form_valid(self, form):
        messages.success(self.request, "La fiche entreprise a été mise à jour.")
        return super().form_valid(form)


class CompanyDetailView(DetailView):
    """Public company page with its open offers."""

    model = Company
    template_name = "accounts/company_detail.html"
    context_object_name = "company"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["job_offers"] = JobOffer.objects.open().filter(company=self.object).prefetch_related("skills")
        return context


class CompanyListView(TemplateView):
    template_name = "accounts/company_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        open_offers = Q(job_offers__is_active=True) & (
            Q(job_offers__deadline__isnull=True) | Q(job_offers__deadline__gte=today)
        )
        context["companies"] = Company.objects.annotate(
            open_offer_count=Count("job_offers", filter=open_offers)
        ).order_by("-open_offer_count", "name")
        return context


class CompanyTeamView(RecruiterRequiredMixin, FormView):
    form_class = CompanyInvitationForm
    template_name = "accounts/company_team.html"
    success_url = reverse_lazy("accounts:company_team")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["company"] = self.get_company()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        company = self.get_company()
        context["company"] = company
        context["members"] = company.recruiters.select_related("user").annotate(offer_count=Count("job_offers"))
        context["invitations"] = company.invitations.filter(accepted_at__isnull=True)
        context["is_admin"] = self.get_recruiter().is_company_admin
        return context

    def form_valid(self, form):
        if not self.get_recruiter().is_company_admin:
            messages.error(self.request, "Seuls les administrateurs peuvent inviter des recruteurs.")
            return redirect("accounts:company_team")
        invitation = form.save(commit=False)
        invitation.company = self.get_company()
        invitation.invited_by = self.request.user
        invitation.save()
        existing = User.objects.filter(email__iexact=invitation.email).first()
        invitation_url = invitation.get_absolute_url()
        if existing:
            notify(
                existing,
                Notification.Kind.INVITATION,
                f"Invitation à rejoindre {invitation.company.name}",
                f"{self.request.user.display_name} vous invite à rejoindre l'équipe de recrutement.",
                invitation_url,
            )
        else:
            link = f"{settings.SITE_URL}{invitation_url}"
            transaction.on_commit(
                lambda: send_email_task.delay(
                    f"[DevHire] Invitation à rejoindre {invitation.company.name}",
                    f"{self.request.user.display_name} vous invite à rejoindre l'équipe de "
                    f"recrutement de {invitation.company.name} sur DevHire.\n\n{link}",
                    [invitation.email],
                )
            )
        messages.success(self.request, f"Invitation envoyée à {invitation.email}.")
        return super().form_valid(form)


class CancelInvitationView(CompanyAdminRequiredMixin, View):
    def post(self, request, pk):
        invitation = get_object_or_404(CompanyInvitation, pk=pk, company=self.get_company(), accepted_at__isnull=True)
        invitation.delete()
        messages.info(request, "Invitation annulée.")
        return redirect("accounts:company_team")


class RemoveMemberView(CompanyAdminRequiredMixin, View):
    """Remove a recruiter from the company — they get a new personal company."""

    def post(self, request, pk):
        member = get_object_or_404(RecruiterProfile, pk=pk, company=self.get_company())
        if member.user_id == request.user.pk:
            messages.error(request, "Vous ne pouvez pas vous retirer vous-même.")
            return redirect("accounts:company_team")
        member.company = Company.objects.create(name=f"Entreprise de {member.user.username}")
        member.company_role = RecruiterProfile.CompanyRole.ADMIN
        member.save(update_fields=["company", "company_role"])
        messages.info(request, f"{member.user.display_name} a été retiré(e) de l'équipe.")
        return redirect("accounts:company_team")


class AcceptInvitationView(View):
    """
    Anonymous visitor  → recruiter sign-up form attached to the company.
    Logged-in recruiter (same email) → joins the company.
    """

    template_name = "accounts/signup_recruiter.html"

    def get_invitation(self, token):
        invitation = get_object_or_404(CompanyInvitation, token=token)
        if not invitation.is_pending:
            return None
        return invitation

    def dispatch(self, request, *args, **kwargs):
        self.invitation = self.get_invitation(kwargs["token"])
        if self.invitation is None:
            messages.error(request, "Cette invitation a expiré ou a déjà été utilisée.")
            return redirect("core:home")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, token):
        if request.user.is_authenticated:
            return self._join_as_existing_user(request)
        form = RecruiterSignUpForm(invitation=self.invitation)
        return self._render(request, form)

    def post(self, request, token):
        if request.user.is_authenticated:
            return self._join_as_existing_user(request)
        form = RecruiterSignUpForm(request.POST, invitation=self.invitation)
        if not form.is_valid():
            return self._render(request, form)
        with transaction.atomic():
            user = form.save()
            self.invitation.accepted_at = timezone.now()
            self.invitation.save(update_fields=["accepted_at"])
        login(request, user, backend=AUTH_BACKEND)
        messages.success(request, f"Bienvenue dans l'équipe {self.invitation.company.name} !")
        return redirect("jobs:recruiter_dashboard")

    def _render(self, request, form):
        return render(request, self.template_name, {"form": form, "invitation": self.invitation})

    @transaction.atomic
    def _join_as_existing_user(self, request):
        user = request.user
        if not user.is_recruiter or user.email.lower() != self.invitation.email.lower():
            messages.error(
                request,
                "Cette invitation est destinée à un autre compte. Déconnectez-vous puis réessayez.",
            )
            return redirect("core:home")
        profile = user.get_recruiter_profile()
        old_company = profile.company
        profile.company = self.invitation.company
        profile.company_role = self.invitation.role
        profile.save(update_fields=["company", "company_role"])
        JobOffer.objects.filter(recruiter=profile, company=old_company).update(company=self.invitation.company)
        if not old_company.recruiters.exists() and not old_company.job_offers.exists():
            old_company.delete()
        self.invitation.accepted_at = timezone.now()
        self.invitation.save(update_fields=["accepted_at"])
        messages.success(request, f"Vous avez rejoint {self.invitation.company.name}.")
        return redirect("jobs:recruiter_dashboard")
