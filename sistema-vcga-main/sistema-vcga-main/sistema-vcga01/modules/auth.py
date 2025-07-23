from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import os
from functools import wraps
from flask import Blueprint
from config import ADMIN_USERNAME1, ADMIN_PASSWORD1

auth_bp = Blueprint('auth', __name__)

# Credenciais fixas do administrador
ADMIN_USERNAME = ADMIN_USERNAME1
ADMIN_PASSWORD = ADMIN_PASSWORD1
ADMIN_USER_ID = "admin_user_001"

def login_required(f):
    """Decorator para rotas que requerem login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Verificar credenciais do administrador
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['user_id'] = ADMIN_USER_ID
            session['username'] = ADMIN_USERNAME
            session['user_role'] = 'admin'
            
            # Criar diretório do usuário se não existir
            user_dir = f'user_data/{ADMIN_USER_ID}'
            os.makedirs(user_dir, exist_ok=True)
            os.makedirs(f'{user_dir}/bases', exist_ok=True)
            os.makedirs(f'{user_dir}/reports', exist_ok=True)
            
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Usuário ou senha incorretos!', 'error')
    
    return render_template('auth/login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Logout realizado com sucesso!', 'success')
    return redirect(url_for('auth.login'))
