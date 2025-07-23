from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
import os
import json
from datetime import datetime

base_bp = Blueprint('base', __name__)

def get_base_status():
    """Retorna o status de todas as bases"""
    bases_status = {}
    for i in range(1, 11):
        if i == 1:
            base_name = "base_vcga.csv"
        else:
            base_name = f"base_vcga{i}.csv"
            
        base_path = os.path.join('dados_matriculas', base_name)
        
        if os.path.exists(base_path):
            try:
                with open(base_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        linhas = content.count('\n') + 1 if content else 0
                        bases_status[f"base{i}"] = {
                            'status': 'completo',
                            'arquivo': base_name,
                            'tamanho': os.path.getsize(base_path),
                            'linhas': linhas,
                            'modificado': datetime.fromtimestamp(os.path.getmtime(base_path)).strftime('%d/%m/%Y %H:%M')
                        }
                    else:
                        bases_status[f"base{i}"] = {'status': 'vazio', 'arquivo': base_name}
            except Exception as e:
                bases_status[f"base{i}"] = {'status': 'erro', 'arquivo': base_name}
        else:
            bases_status[f"base{i}"] = {'status': 'inexistente', 'arquivo': base_name}
    
    return bases_status

@base_bp.route('/')
def bases_config():
    bases_status = get_base_status()
    return render_template('bases.html', bases_status=bases_status)

@base_bp.route('/status')
def get_status():
    return jsonify(get_base_status())

@base_bp.route('/delete/<int:base_number>', methods=['POST'])
def delete_base(base_number):
    try:
        if base_number < 1 or base_number > 10:
            return jsonify({'success': False, 'message': 'Número da base inválido'})
        
        if base_number == 1:
            output_filename = "base_vcga.csv"
        else:
            output_filename = f"base_vcga{base_number}.csv"
            
        output_path = os.path.join('dados_matriculas', output_filename)
        
        if os.path.exists(output_path):
            os.remove(output_path)
            return jsonify({'success': True, 'message': f'Base {base_number} removida com sucesso!'})
        else:
            return jsonify({'success': False, 'message': f'Base {base_number} não encontrada'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erro ao remover base: {str(e)}'})
