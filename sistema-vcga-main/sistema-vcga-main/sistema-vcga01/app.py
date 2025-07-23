from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from werkzeug.utils import secure_filename
import os
import logging
from datetime import datetime

# Importar módulos do sistema
from modules.auth import auth_bp, login_required
from modules.whatsapp_manager import whatsapp_bp
from modules.data_converter import converter_bp
from modules.base_manager import base_bp
from modules.bot_manager import bot_bp
from modules.report_manager import report_bp

def create_app():
    app = Flask(__name__)
    app.secret_key = 'vcga_secret_key_2024'
    
    # Configurações
    app.config['UPLOAD_FOLDER'] = 'uploads'
    app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # Aumentar para 50MB
    
    # Criar diretórios necessários
    os.makedirs('uploads', exist_ok=True)
    os.makedirs('dados_matriculas', exist_ok=True)
    os.makedirs('user_data', exist_ok=True)
    os.makedirs('logs', exist_ok=True)
    
    # Configurar logging com UTF-8
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("logs/app.log", encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

    # Configurar o handler do console para UTF-8
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)

    # Configurar encoding para UTF-8 se possível
    try:
        import sys
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass
    
    # Registrar blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(whatsapp_bp, url_prefix='/whatsapp')
    app.register_blueprint(converter_bp, url_prefix='/converter')
    app.register_blueprint(base_bp, url_prefix='/bases')
    app.register_blueprint(bot_bp, url_prefix='/bot')
    app.register_blueprint(report_bp, url_prefix='/reports')
    
    # Rota principal
    @app.route('/')
    @login_required
    def index():
        from modules.whatsapp_manager import get_whatsapp_status
        from modules.bot_manager import get_bot_status
        
        whatsapp_status = get_whatsapp_status()
        bot_status = get_bot_status()
        
        return render_template('dashboard.html', 
                             whatsapp_status=whatsapp_status,
                             bot_status=bot_status,
                             user_name=session.get('username', 'Admin'))
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
