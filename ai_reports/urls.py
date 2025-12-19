from django.urls import path
from .views import GenerateSQLView, TestAIView, DatabaseSchemaView,GenerateChartView

app_name = 'ai_reports'

urlpatterns = [
    path('generate-sql/', GenerateSQLView.as_view(), name='generate-sql'),
    path('test/', TestAIView.as_view(), name='test'),
    path('schema/', DatabaseSchemaView.as_view(), name='schema'),  # New
    path('generate-chart/', GenerateChartView.as_view(), name='generate-chart'),
]