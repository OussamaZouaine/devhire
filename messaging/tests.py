from django.core import mail
from django.test import TestCase
from django.urls import reverse

from core.factories import PASSWORD, make_application, make_candidate, make_offer, make_recruiter

from .models import Message, Notification


class MessagingTests(TestCase):
    def setUp(self):
        self.recruiter = make_recruiter("rec")
        self.offer = make_offer(self.recruiter)
        self.candidate = make_candidate("alice")
        self.application = make_application(self.candidate, self.offer)
        self.thread_url = reverse("messaging:thread", args=[self.application.pk])

    def test_candidate_message_notifies_recruiters(self):
        self.client.login(username="alice", password=PASSWORD)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.thread_url, {"body": "Bonjour !"})
        self.assertRedirects(response, self.thread_url)
        self.assertEqual(Message.objects.get().sender, self.candidate)
        self.assertTrue(Notification.objects.filter(recipient=self.recruiter, kind="message").exists())
        self.assertEqual(len(mail.outbox), 1)

    def test_recruiter_reply_with_htmx_and_read_receipts(self):
        Message.objects.create(application=self.application, sender=self.candidate, body="Hello")
        self.client.login(username="rec", password=PASSWORD)
        inbox = self.client.get(reverse("messaging:inbox"))
        self.assertEqual(inbox.context["conversations"][0].unread, 1)

        response = self.client.post(self.thread_url, {"body": "Réponse"}, HTTP_HX_REQUEST="true")
        self.assertTemplateUsed(response, "messaging/partials/messages.html")
        self.assertTrue(Notification.objects.filter(recipient=self.candidate).exists())

        self.client.get(reverse("messaging:thread_messages", args=[self.application.pk]))
        self.assertIsNotNone(Message.objects.get(body="Hello").read_at)

    def test_empty_or_too_long_message(self):
        self.client.login(username="alice", password=PASSWORD)
        self.client.post(self.thread_url, {"body": "   "})
        self.client.post(self.thread_url, {"body": "x" * 5001})
        self.assertFalse(Message.objects.exists())

    def test_strangers_cannot_read_thread(self):
        make_candidate("bob")
        self.client.login(username="bob", password=PASSWORD)
        self.assertEqual(self.client.get(self.thread_url).status_code, 403)
        make_recruiter("other")
        self.client.login(username="other", password=PASSWORD)
        self.assertEqual(self.client.get(self.thread_url).status_code, 403)


class NotificationTests(TestCase):
    def setUp(self):
        self.user = make_candidate("alice")
        self.client.login(username="alice", password=PASSWORD)
        self.notification = Notification.objects.create(
            recipient=self.user, kind="message", title="Hello", url=reverse("core:candidate_dashboard")
        )

    def test_bell_and_list(self):
        response = self.client.get(reverse("messaging:notification_bell"))
        self.assertEqual(response.context["unread_count"], 1)
        self.assertContains(self.client.get(reverse("messaging:notifications")), "Hello")

    def test_open_marks_read_and_redirects_safely(self):
        response = self.client.get(reverse("messaging:open_notification", args=[self.notification.pk]))
        self.assertRedirects(response, reverse("core:candidate_dashboard"))
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_read)

        evil = Notification.objects.create(recipient=self.user, kind="message", title="x", url="https://evil.com")
        response = self.client.get(reverse("messaging:open_notification", args=[evil.pk]))
        self.assertRedirects(response, reverse("messaging:notifications"))

    def test_mark_all_read(self):
        self.client.post(reverse("messaging:mark_all_read"))
        self.assertFalse(Notification.objects.filter(is_read=False).exists())
        Notification.objects.update(is_read=False)
        response = self.client.post(reverse("messaging:mark_all_read"), HTTP_HX_REQUEST="true")
        self.assertTemplateUsed(response, "messaging/partials/bell.html")

    def test_cannot_open_other_users_notification(self):
        make_candidate("bob")
        self.client.login(username="bob", password=PASSWORD)
        response = self.client.get(reverse("messaging:open_notification", args=[self.notification.pk]))
        self.assertEqual(response.status_code, 404)
