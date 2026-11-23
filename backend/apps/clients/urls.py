from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("clients", views.ClientViewSet, basename="client")
router.register(
    r"clients/(?P<client_id>[0-9a-f-]{36})/contacts", views.ClientContactViewSet, basename="client-contact"
)
router.register("agencies", views.AgencyViewSet, basename="agency")

urlpatterns = router.urls
