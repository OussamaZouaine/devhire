from django.urls import path

from . import views

app_name = "messaging"

urlpatterns = [
    path("", views.InboxView.as_view(), name="inbox"),
    path("candidature/<int:pk>/", views.ThreadView.as_view(), name="thread"),
    path("candidature/<int:pk>/messages/", views.ThreadMessagesPartialView.as_view(), name="thread_messages"),
    path("notifications/", views.NotificationListView.as_view(), name="notifications"),
    path("notifications/cloche/", views.NotificationBellView.as_view(), name="notification_bell"),
    path("notifications/tout-lire/", views.MarkAllNotificationsReadView.as_view(), name="mark_all_read"),
    path("notifications/<int:pk>/", views.OpenNotificationView.as_view(), name="open_notification"),
]
