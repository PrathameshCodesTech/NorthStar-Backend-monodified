from rest_framework import serializers


class AskQuestionSerializer(serializers.Serializer):
    """Serializer for AI question requests"""
    
    question = serializers.CharField(
        max_length=500,
        help_text="Natural language question about your data"
    )
    
    ai_choice = serializers.ChoiceField(
        choices=['auto', 'ollama', 'gemini'],
        default='auto',
        help_text="Which AI to use"
    )


class SQLResponseSerializer(serializers.Serializer):
    """Serializer for SQL generation response"""
    
    question = serializers.CharField()
    generated_sql = serializers.CharField()
    ai_used = serializers.CharField()
    results = serializers.ListField(required=False)
    columns = serializers.ListField(required=False)
    error = serializers.CharField(required=False)