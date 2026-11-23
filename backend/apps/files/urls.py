from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import DocumentViewSet, DownloadView

router = DefaultRouter()
router.register("files", DocumentViewSet, basename="file")

urlpatterns = [
    path("files/download/<str:token>/", DownloadView.as_view(), name="file-download"),
    *router.urls,
]
