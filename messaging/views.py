from django.contrib import messages as flash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Max, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import ListView

from applications.models import Application

from .models import Message, Notification
from .services import notify, notify_company

MAX_MESSAGE_LENGTH = 5000


def accessible_applications(user):
    if user.is_candidate:
        return Application.objects.filter(candidate__user=user)
    if user.is_recruiter:
        return Application.objects.filter(job_offer__company=user.get_recruiter_profile().company)
    return Application.objects.none()


class InboxView(LoginRequiredMixin, ListView):
    template_name = "messaging/inbox.html"
    context_object_name = "conversations"

    def get_queryset(self):
        user = self.request.user
        return (
            accessible_applications(user)
            .filter(messages__isnull=False)
            .annotate(
                last_message_at=Max("messages__created_at"),
                unread=Count(
                    "messages",
                    filter=Q(messages__read_at__isnull=True) & ~Q(messages__sender=user),
                ),
            )
            .select_related("job_offer__company", "candidate__user")
            .order_by("-last_message_at")
        )


class ThreadMixin(LoginRequiredMixin):
    def get_application(self, pk):
        application = get_object_or_404(
            Application.objects.select_related("job_offer__company", "candidate__user"), pk=pk
        )
        if not accessible_applications(self.request.user).filter(pk=pk).exists():
            raise PermissionDenied
        return application

    def mark_read(self, application):
        application.messages.filter(read_at__isnull=True).exclude(sender=self.request.user).update(
            read_at=timezone.now()
        )


class ThreadView(ThreadMixin, View):
    template_name = "messaging/thread.html"

    def get(self, request, pk):
        application = self.get_application(pk)
        self.mark_read(application)
        return render(
            request,
            self.template_name,
            {
                "application": application,
                "thread_messages": application.messages.select_related("sender"),
                "max_length": MAX_MESSAGE_LENGTH,
            },
        )

    def post(self, request, pk):
        application = self.get_application(pk)
        body = request.POST.get("body", "").strip()
        if not body:
            flash.error(request, "Le message est vide.")
        elif len(body) > MAX_MESSAGE_LENGTH:
            flash.error(request, f"Le message ne doit pas dépasser {MAX_MESSAGE_LENGTH} caractères.")
        else:
            Message.objects.create(application=application, sender=request.user, body=body)
            url = reverse("messaging:thread", kwargs={"pk": application.pk})
            title = f"Nouveau message — {application.job_offer.title}"
            preview = f"{request.user.display_name} : {body[:200]}"
            if request.user.is_candidate:
                notify_company(application.job_offer.company, Notification.Kind.MESSAGE, title, preview, url)
            else:
                notify(application.candidate.user, Notification.Kind.MESSAGE, title, preview, url)
        if request.headers.get("HX-Request"):
            return self.render_messages(request, application)
        return redirect("messaging:thread", pk=application.pk)

    @staticmethod
    def render_messages(request, application):
        return render(
            request,
            "messaging/partials/messages.html",
            {"thread_messages": application.messages.select_related("sender"), "application": application},
        )


class ThreadMessagesPartialView(ThreadMixin, View):
    """Polled by HTMX every few seconds to refresh the conversation."""

    def get(self, request, pk):
        application = self.get_application(pk)
        self.mark_read(application)
        return ThreadView.render_messages(request, application)


class NotificationListView(LoginRequiredMixin, ListView):
    template_name = "messaging/notifications.html"
    context_object_name = "notifications"
    paginate_by = 20

    def get_queryset(self):
        return self.request.user.notifications.all()


class OpenNotificationView(LoginRequiredMixin, View):
    def get(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=["is_read"])
        target = notification.url
        if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
            return redirect(target)
        return redirect("messaging:notifications")


class MarkAllNotificationsReadView(LoginRequiredMixin, View):
    def post(self, request):
        request.user.notifications.filter(is_read=False).update(is_read=True)
        if request.headers.get("HX-Request"):
            return NotificationBellView().get(request)
        return redirect("messaging:notifications")


class NotificationBellView(LoginRequiredMixin, View):
    """Navbar bell (count + latest notifications), refreshed by HTMX polling."""

    def get(self, request):
        user = request.user
        unread_messages = (
            Message.objects.filter(application__in=accessible_applications(user), read_at__isnull=True)
            .exclude(sender=user)
            .count()
        )
        return render(
            request,
            "messaging/partials/bell.html",
            {
                "unread_count": user.notifications.filter(is_read=False).count(),
                "latest": user.notifications.all()[:6],
                "unread_messages": unread_messages,
            },
        )
