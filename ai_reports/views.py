from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .utils import (
    generate_sql_gemini, 
    validate_sql, 
    execute_query,
    generate_chart_config,
    get_database_schema
)
from .gemini_config import GEMINI_MODEL_NAME, get_model_info  # ✅ Import model info
import time
import logging

logger = logging.getLogger(__name__)


class GenerateSQLView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        question = request.data.get('question', '').strip()
        database = request.data.get('database', 'default')
        
        if not question:
            return Response(
                {'error': 'Question is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Generate SQL
            start_time = time.time()
            sql = generate_sql_gemini(question, database)
            generation_time = time.time() - start_time
            
            # Validate SQL
            is_valid, message = validate_sql(sql)
            if not is_valid:
                return Response(
                    {'error': f'Invalid SQL: {message}'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Execute query
            results, columns = execute_query(sql, database)
            
            # Serialize datetime/date objects
            for row in results:
                for key, value in row.items():
                    if hasattr(value, 'isoformat'):
                        row[key] = value.isoformat()
            
            return Response({
                'question': question,
                'generated_sql': sql,
                'results': results,
                'columns': columns,
                'count': len(results),
                'generation_time': round(generation_time, 2),
                'ai_used': 'gemini',
                'model_name': GEMINI_MODEL_NAME  # ✅ Include model name
            })
            
        except Exception as e:
            logger.error(f"Error in GenerateSQLView: {str(e)}")
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class GenerateChartView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        question = request.data.get('question', '').strip()
        database = request.data.get('database', 'default')
        
        if not question:
            return Response(
                {'error': 'Question is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Generate SQL
            start_time = time.time()
            sql = generate_sql_gemini(question, database)
            
            # Validate SQL
            is_valid, message = validate_sql(sql)
            if not is_valid:
                return Response(
                    {'error': f'Invalid SQL: {message}'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Execute query
            results, columns = execute_query(sql, database)
            
            # Serialize datetime/date objects
            for row in results:
                for key, value in row.items():
                    if hasattr(value, 'isoformat'):
                        row[key] = value.isoformat()
            
            # Generate chart configuration
            chart_config = generate_chart_config(question, results, columns)
            
            generation_time = time.time() - start_time
            
            return Response({
                'question': question,
                'generated_sql': sql,
                'results': results,
                'columns': columns,
                'count': len(results),
                'chartConfig': chart_config,
                'generation_time': round(generation_time, 2),
                'ai_used': 'gemini',
                'model_name': GEMINI_MODEL_NAME  # ✅ Include model name
            })
            
        except Exception as e:
            logger.error(f"Error in GenerateChartView: {str(e)}")
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TestAIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        from django.conf import settings
        
        # ✅ Get detailed model info
        model_info = get_model_info()
        
        return Response({
            'gemini_enabled': bool(settings.GEMINI_API_KEY),
            'gemini_configured': bool(settings.GEMINI_API_KEY),
            'model_name': GEMINI_MODEL_NAME,  # ✅ Current model
            'model_info': model_info  # ✅ Detailed info
        })


class DatabaseSchemaView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        database = request.query_params.get('database', 'default')
        schema = get_database_schema(database)
        return Response({'schema': schema})