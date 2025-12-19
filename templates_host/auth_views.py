"""
Authentication views for SuperAdmin login
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken


@api_view(['POST'])
@permission_classes([AllowAny])  # Anyone can try to login
def login_view(request):
    """
    SuperAdmin login endpoint
    
    POST /api/v1/templates/auth/login/
    {
        "username": "admin",
        "password": "123"
    }
    
    Returns JWT tokens + user info
    """
    username = request.data.get('username')
    password = request.data.get('password')
    
    # Validate input
    if not username or not password:
        return Response(
            {'error': 'Username and password are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Authenticate user
    user = authenticate(username=username, password=password)
    
    if user is None:
        return Response(
            {'error': 'Invalid credentials'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    # Check if superuser
    if not user.is_superuser:
        return Response(
            {'error': 'Access denied. SuperAdmin privileges required.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Generate JWT tokens
    refresh = RefreshToken.for_user(user)
    
    return Response({
        'success': True,
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'is_superuser': user.is_superuser,
        }
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def logout_view(request):
    """
    Logout endpoint (optional - mainly handled client-side)
    """
    return Response({
        'success': True,
        'message': 'Logged out successfully'
    })
