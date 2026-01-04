"""
Authentication Routes
Handles login, logout, and user verification
"""

from flask import Blueprint, request, jsonify
import bcrypt
from backend.db import get_db
from backend.auth.jwt_utils import generate_token

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@auth_bp.route('/login', methods=['POST'])
def login():
    """
    User login endpoint
    POST /api/auth/login
    Body: {"email": "user@example.com", "password": "password"}
    """
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'error': 'Email and password required'}), 400
        
        # Get database connection
        db = get_db()
        
        # Find user by email
        user = db.execute_query(
            "SELECT user_id, name, email, password_hash, role FROM users WHERE email = %s",
            (email,),
            fetch_one=True
        )
        
        if not user:
            return jsonify({'error': 'Invalid email or password'}), 401
        
        # Verify password (password_hash is stored as string, convert back to bytes)
        stored_hash = user['password_hash']
        if isinstance(stored_hash, str):
            stored_hash = stored_hash.encode('utf-8')
        
        password_valid = bcrypt.checkpw(
            password.encode('utf-8'),
            stored_hash
        )
        
        if not password_valid:
            return jsonify({'error': 'Invalid email or password'}), 401
        
        # Generate JWT token
        token = generate_token(
            user['user_id'],
            user['email'],
            user['role'],
            user['name']
        )
        
        # Get user's assigned areas
        areas = db.execute_query(
            """
            SELECT a.area_id, a.area_name 
            FROM areas a
            JOIN user_areas ua ON a.area_id = ua.area_id
            WHERE ua.user_id = %s
            """,
            (user['user_id'],),
            fetch=True
        )
        
        return jsonify({
            'success': True,
            'token': token,
            'user': {
                'user_id': user['user_id'],
                'name': user['name'],
                'email': user['email'],
                'role': user['role'],
                'areas': [area['area_name'] for area in (areas or [])]
            }
        }), 200
        
    except Exception as e:
        print(f"❌ Login error: {e}")
        return jsonify({'error': 'Login failed'}), 500

@auth_bp.route('/logout', methods=['POST'])
def logout():
    """
    User logout endpoint (frontend clears token)
    POST /api/auth/logout
    """
    return jsonify({'success': True, 'message': 'Logged out successfully'}), 200

@auth_bp.route('/verify', methods=['GET'])
def verify():
    """
    Verify if token is valid
    GET /api/auth/verify
    Headers: Authorization: Bearer <token>
    """
    from backend.auth.jwt_utils import decode_token
    
    token = None
    if 'Authorization' in request.headers:
        try:
            token = request.headers['Authorization'].split(' ')[1]
        except IndexError:
            return jsonify({'valid': False}), 401
    
    if not token:
        return jsonify({'valid': False}), 401
    
    payload = decode_token(token)
    if not payload:
        return jsonify({'valid': False}), 401
    
    return jsonify({
        'valid': True,
        'user': {
            'user_id': payload['user_id'],
            'email': payload['email'],
            'role': payload['role'],
            'name': payload['name']
        }
    }), 200
