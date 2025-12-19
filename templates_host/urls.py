from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from . import auth_views  # ← ADD THIS

app_name = 'templates_host'

router = DefaultRouter()
router.register(r'framework-categories', views.FrameworkCategoryViewSet, basename='framework-category')
router.register(r'frameworks', views.FrameworkViewSet, basename='framework')
router.register(r'domains', views.DomainViewSet, basename='domain')
router.register(r'categories', views.CategoryViewSet, basename='category')
router.register(r'subcategories', views.SubcategoryViewSet, basename='subcategory')
router.register(r'controls', views.ControlViewSet, basename='control')
router.register(r'questions', views.AssessmentQuestionViewSet, basename='question')
router.register(r'evidence', views.EvidenceRequirementViewSet, basename='evidence')

urlpatterns = [
    path('', include(router.urls)),
    
    # ← ADD THESE TWO LINES:
    path('auth/login/', auth_views.login_view, name='login'),
    path('auth/logout/', auth_views.logout_view, name='logout'),
]