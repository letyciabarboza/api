from flask import Blueprint, request, jsonify, session, flash, redirect, url_for
from werkzeug.utils import secure_filename
import pandas as pd
import json
import csv
import os
import re
import logging

converter_bp = Blueprint('converter', __name__)

ALLOWED_EXTENSIONS = {'xls', 'xlsx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class ConversorDados:
    def __init__(self, nome_arquivo_planilha, nome_arquivo_csv):
        self.nome_arquivo_planilha = nome_arquivo_planilha
        self.nome_arquivo_csv = nome_arquivo_csv

    def formatar_coordenadas(self, valor):
        if pd.isna(valor) or valor == '' or valor is None:
            return ""
        try:
            valor_str = str(valor).strip().replace(",", ".")
            valor_limpo = re.sub(r'[^\d\.\-]', '', valor_str)
            
            if not valor_limpo:
                return ""
                
            valor_float = float(valor_limpo)
            
            if abs(valor_float) > 1000:
                valor_float = valor_float / 1_000_000
                
            return f"{valor_float:.6f}"
        except (ValueError, TypeError) as e:
            logging.warning(f"Erro ao formatar coordenada '{valor}': {e}")
            return ""

    def salvar_csv_formatado(self, dados_dict):
        try:
            dir_path = os.path.dirname(self.nome_arquivo_csv)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            
            logging.info(f"Salvando {len(dados_dict)} registros em: {self.nome_arquivo_csv}")
            
            with open(self.nome_arquivo_csv, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile, quoting=csv.QUOTE_ALL)
                
                for chave, dados in dados_dict.items():
                    json_string = json.dumps(dados, ensure_ascii=False)
                    writer.writerow([chave, json_string])
            
            if os.path.exists(self.nome_arquivo_csv):
                file_size = os.path.getsize(self.nome_arquivo_csv)
                logging.info(f"Arquivo CSV criado com sucesso: {self.nome_arquivo_csv} ({file_size} bytes)")
                return True
            else:
                logging.error("Arquivo CSV não foi criado")
                return False
                
        except Exception as e:
            logging.error(f"Erro ao salvar CSV: {e}")
            return False

    def detectar_colunas(self, planilha):
        """Detecta automaticamente as colunas da planilha"""
        colunas_encontradas = {}
        colunas_disponiveis = [str(col).strip().upper() for col in planilha.columns]
        
        logging.info(f"Colunas disponíveis na planilha: {colunas_disponiveis}")
        
        mapeamento = {
            'HD': ['Nº DO HIDROMETRO', 'HD', 'HIDROMETRO', 'NUMERO_HIDROMETRO', 'NUM_HIDROMETRO'],
            'MATRICULA': ['NUM_LIGACAO', 'MATRICULA', 'NUMERO_LIGACAO', 'COD_LIGACAO', 'LIGACAO'],
            'NOME': ['NOME', 'CLIENTE', 'NOME_CLIENTE', 'NOME DO CLIENTE'],
            'ENDERECO': ['RUA ENTREGA', 'ENDERECO', 'RUA', 'LOGRADOURO', 'ENDEREÇO'],
            'CIDADE': ['CIDADE ENTREGA', 'CIDADE'],
            'BAIRRO': ['BAIRRO ENTREGA', 'BAIRRO'],
            'CLASSIFICACAO': ['CLASSIFICAÇÃO', 'CLASSIFICACAO', 'CLASSE'],
            'LATITUDE': ['LATITUDE', 'LAT'],
            'LONGITUDE': ['LONGITUDE', 'LONG', 'LNG', 'LON']
        }
        
        for campo, possiveis_nomes in mapeamento.items():
            for nome_possivel in possiveis_nomes:
                if nome_possivel.upper() in colunas_disponiveis:
                    for col_original in planilha.columns:
                        if str(col_original).strip().upper() == nome_possivel.upper():
                            colunas_encontradas[campo] = col_original
                            break
                    break
        
        logging.info(f"Colunas mapeadas: {colunas_encontradas}")
        return colunas_encontradas

    def converter_para_csv(self):
        try:
            logging.info(f"=== INICIANDO CONVERSÃO ===")
            logging.info(f"Arquivo de entrada: {self.nome_arquivo_planilha}")
            logging.info(f"Arquivo de saída: {self.nome_arquivo_csv}")
            
            if not os.path.exists(self.nome_arquivo_planilha):
                logging.error(f"Arquivo não encontrado: {self.nome_arquivo_planilha}")
                return False
            
            try:
                logging.info("Tentando ler com openpyxl (.xlsx)...")
                planilha = pd.read_excel(self.nome_arquivo_planilha, engine='openpyxl')
                logging.info("✅ Planilha lida com openpyxl")
            except Exception as e1:
                logging.warning(f"Falha com openpyxl: {e1}")
                try:
                    logging.info("Tentando ler com xlrd (.xls)...")
                    planilha = pd.read_excel(self.nome_arquivo_planilha, engine='xlrd')
                    logging.info("✅ Planilha lida com xlrd")
                except Exception as e2:
                    logging.error(f"Falha com xlrd: {e2}")
                    return False
            
            logging.info(f"📊 Planilha carregada: {len(planilha)} linhas x {len(planilha.columns)} colunas")
            
            colunas_encontradas = self.detectar_colunas(planilha)
            
            if not colunas_encontradas:
                logging.error("❌ Nenhuma coluna reconhecida foi encontrada")
                return False
            
            dados_json = {}
            linhas_processadas = 0
            linhas_com_erro = 0
            
            logging.info("🔄 Processando linhas...")
            
            for index, row in planilha.iterrows():
                try:
                    HD = ""
                    matricula = ""
                    
                    if 'HD' in colunas_encontradas:
                        hd_valor = row.get(colunas_encontradas['HD'])
                        if pd.notna(hd_valor) and str(hd_valor).strip() != '':
                            HD = str(hd_valor).strip().upper()
                    
                    if 'MATRICULA' in colunas_encontradas:
                        mat_valor = row.get(colunas_encontradas['MATRICULA'])
                        if pd.notna(mat_valor) and str(mat_valor).strip() != '':
                            matricula = str(mat_valor).strip()
                    
                    if not HD and not matricula:
                        continue
                    
                    dados_comuns = {
                        "Matricula": matricula,
                        "Cliente": str(row.get(colunas_encontradas.get('NOME', ''), '')).strip(),
                        "Endereço": str(row.get(colunas_encontradas.get('ENDERECO', ''), '')).strip(),
                        "Cidade": str(row.get(colunas_encontradas.get('CIDADE', ''), '')).strip(),
                        "Bairro": str(row.get(colunas_encontradas.get('BAIRRO', ''), '')).strip(),
                        "Classificação": str(row.get(colunas_encontradas.get('CLASSIFICACAO', ''), '')).strip(),
                        "Latitude": self.formatar_coordenadas(row.get(colunas_encontradas.get('LATITUDE', ''))),
                        "Longitude": self.formatar_coordenadas(row.get(colunas_encontradas.get('LONGITUDE', '')))
                    }
                    
                    if HD and HD.lower() not in ['nan', 'none', '']:
                        dados_json[HD] = {"HD": HD, **dados_comuns}
                    
                    if matricula and matricula.lower() not in ['nan', 'none', '']:
                        dados_json[matricula] = dados_comuns
                    
                    linhas_processadas += 1
                    
                    if linhas_processadas % 100 == 0:
                        logging.info(f"Processadas {linhas_processadas} linhas...")
                    
                except Exception as e:
                    linhas_com_erro += 1
                    logging.warning(f"Erro ao processar linha {index + 1}: {e}")
                    continue
            
            logging.info(f"✅ Processamento concluído:")
            logging.info(f"   - Linhas processadas: {linhas_processadas}")
            logging.info(f"   - Linhas com erro: {linhas_com_erro}")
            logging.info(f"   - Registros gerados: {len(dados_json)}")
            
            if len(dados_json) == 0:
                logging.error("❌ Nenhum registro válido foi gerado")
                return False
            
            if self.salvar_csv_formatado(dados_json):
                logging.info("✅ Conversão concluída com sucesso!")
                return True
            else:
                logging.error("❌ Erro ao salvar arquivo CSV")
                return False
                
        except Exception as e:
            logging.error(f"❌ Erro geral na conversão: {e}")
            return False

@converter_bp.route('/convert', methods=['POST'])
def convert_file():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'Nenhum arquivo enviado'})
    
    file = request.files['file']
    base_number = request.form.get('base_number')
    
    if file.filename == '':
        return jsonify({'success': False, 'message': 'Nenhum arquivo selecionado'})
    
    if not base_number or not base_number.isdigit() or int(base_number) < 1 or int(base_number) > 10:
        return jsonify({'success': False, 'message': 'Número da base inválido'})
    
    if file and allowed_file(file.filename):
        try:
            # Salvar arquivo temporário
            filename = secure_filename(file.filename)
            temp_path = os.path.join('uploads', filename)
            file.save(temp_path)
            
            # Definir arquivo de saída
            base_num = int(base_number)
            if base_num == 1:
                output_filename = "base_vcga.csv"
            else:
                output_filename = f"base_vcga{base_num}.csv"
            
            output_path = os.path.join('dados_matriculas', output_filename)
            
            # Converter
            conversor = ConversorDados(temp_path, output_path)
            
            if conversor.converter_para_csv():
                # Remover arquivo temporário
                try:
                    os.remove(temp_path)
                except:
                    pass
                
                if os.path.exists(output_path):
                    file_size = os.path.getsize(output_path)
                    with open(output_path, 'r', encoding='utf-8') as f:
                        linhas = sum(1 for line in f)
                    
                    return jsonify({
                        'success': True, 
                        'message': f'Base {base_number} convertida com sucesso!',
                        'records': linhas,
                        'size': file_size
                    })
                else:
                    return jsonify({'success': False, 'message': 'Erro: Arquivo CSV não foi criado'})
            else:
                return jsonify({'success': False, 'message': 'Erro ao converter planilha'})
                
        except Exception as e:
            logging.error(f"Erro no upload: {e}")
            return jsonify({'success': False, 'message': f'Erro ao processar arquivo: {str(e)}'})
    else:
        return jsonify({'success': False, 'message': 'Tipo de arquivo não permitido'})
