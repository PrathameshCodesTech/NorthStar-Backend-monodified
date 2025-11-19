from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'company_compliance'

router = DefaultRouter()
router.register(r'frameworks', views.CompanyFrameworkViewSet, basename='company-framework')
router.register(r'controls', views.CompanyControlViewSet, basename='company-control')
router.register(r'assignments', views.ControlAssignmentViewSet, basename='control-assignment')
router.register(r'campaigns', views.AssessmentCampaignViewSet, basename='assessment-campaign')
router.register(r'responses', views.AssessmentResponseViewSet, basename='assessment-response')
router.register(r'evidence', views.EvidenceDocumentViewSet, basename='evidence-document')
router.register(r'reports', views.ComplianceReportViewSet, basename='compliance-report')

urlpatterns = [
    path('', include(router.urls)),
]