from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views, views_facility_agent

# Create router for ViewSet URLs
router = DefaultRouter()
router.register(r'facilities', views.FacilityViewSet, basename='facility')
router.register(r'agent', views_facility_agent.FacilityAgentViewSet, basename='facility-agent')

app_name = 'facilities'

urlpatterns = [
    # API URLs using ViewSet router
    path('api/', include(router.urls)),
]