"""
JWT Utilities for Token Generation and Verification
"""

import jwt
import datetime
from functools import wraps
from flask import request, jsonify
import os

# Secret key for JWT - should be in environment variable in production
SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'crowdcount-secret-key-change-in-production')
ALGORITHM = 'HS256'
TOKEN_EXPIRY_HOURS = 24

def generate_token(user_id, email, role, name):
    """Generate JWT token for authenticated user"""
    payload = {
        'user_id': user_id,
        'email': email,
        'role': role,
        'name': name,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=TOKEN_EXPIRY_HOURS),
        'iat': datetime.datetime.utcnow()
    }
    
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token

def decode_token(token):
    """Decode and verify JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def token_required(f):
    """Decorator to protect routes with JWT authentication"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Get token from Authorization header
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(' ')[1]  # Bearer <token>
            except IndexError:
                return jsonify({'error': 'Invalid token format'}), 401
        
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        
        # Verify token
        payload = decode_token(token)
        if not payload:
            return jsonify({'error': 'Token is invalid or expired'}), 401
        
        # Pass user info to route
        request.current_user = payload
        return f(*args, **kwargs)
    
    return decorated

def admin_required(f):
    """Decorator to restrict access to admin users only"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Get token from Authorization header
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(' ')[1]
            except IndexError:
                return jsonify({'error': 'Invalid token format'}), 401
        
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        
        # Verify token
        payload = decode_token(token)
        if not payload:
            return jsonify({'error': 'Token is invalid or expired'}), 401
        
        # Check if user is admin
        if payload.get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        # Pass user info to route
        request.current_user = payload
        return f(*args, **kwargs)
    
    return decorated
