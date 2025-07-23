from flask import Blueprint, request, jsonify, session
import threading
import time
import requests
import logging
import json
import os
import csv
from datetime import datetime
import schedule
import re
import config

bot_bp = Blueprint('bot', __name__)

# Variáveis globais para o bot único
bot_thread = None
is_bot_running = False

def clean_text_for_log(text):
    """Remove emojis e caracteres especiais para logging seguro"""
    if not text:
        return ""
    # Remove emojis e caracteres especiais, mantém apenas alfanuméricos, espaços e pontuação básica
    clean_text = re.sub(r'[^\w\s\-\.\,\:\;\!\?$$$$\/]', '', str(text))
    return clean_text.strip()

def get_bot_status():
    """Retorna o status do bot"""
    return {
        'running': is_bot_running,
        'last_activity': datetime.now().isoformat() if is_bot_running else None
    }

class ChatBot:
    base_url = 'http://localhost:3000'
    
    def __init__(self, arquivo_contadores="contadores.json"):
        logging.info("Inicializando ChatBot VCGA-LeituraAE")
        
        self.digitdocliente = ["ola", "olá", "bom dia", "oi", "boa tarde", "boa noite", "foto", "foto da fachada", "fachada", "faxada", "pode me ajudar", "ajuda", "imagem"]
        self.arquivo_contadores = arquivo_contadores
        self.carregar_contadores()
        
        # Carregar links do config
        self.msg_links = [
            config.msg_link_enviar_1,
            config.msg_link_enviar_2,
            config.msg_link_enviar_3,
            config.msg_link_enviar_4,
            config.msg_link_enviar_5,
            config.msg_link_enviar_6,
            config.msg_link_enviar_7
        ]
        
    def carregar_contadores(self):
        if os.path.exists(self.arquivo_contadores):
            with open(self.arquivo_contadores, 'r', encoding='utf-8') as file:
                try:
                    dados = json.load(file)
                    self.total_respostas_parecer = dados.get("total_respostas_parecer", 0)
                    self.total_hd_encontrado = dados.get("total_hd_encontrado", 0)
                    self.total_matriculas_encontradas = dados.get("total_matriculas_encontradas", 0)
                    self.total_hd_nao_encontrado = dados.get("total_hd_nao_encontrado", 0)
                    self.total_mensagens_invalidas = dados.get("total_mensagens_invalidas", 0)
                    self.total_respostas_link = dados.get("total_respostas_link", 0) 
                    self.total_matriculas_nao_encontrada = dados.get("total_matriculas_nao_encontrada", 0)
                    self.total_mesagens_respondidas = dados.get("total_mesagens_respondidas", 0)
                    self.ultima_data = dados.get("ultima_data", None)

                    if self.ultima_data:
                        self.ultima_data = datetime.strptime(self.ultima_data, "%Y-%m-%d")

                    self.verificar_novo_dia()

                except json.JSONDecodeError:
                    logging.error("Erro ao ler o arquivo de contadores. Inicializando os contadores como 0.")
                    self.inicializar_contadores()
        else:
            logging.info("Arquivo de contadores não encontrado. Inicializando os contadores como 0.")
            self.inicializar_contadores()

    def inicializar_contadores(self):
        self.total_hd_encontrado = 0
        self.total_matriculas_encontradas = 0
        self.total_hd_nao_encontrado = 0
        self.total_mensagens_invalidas = 0
        self.total_respostas_link = 0
        self.total_matriculas_nao_encontrada = 0
        self.total_mesagens_respondidas = 0
        self.ultima_data = datetime.now().date()

    def verificar_novo_dia(self):
        data_atual = datetime.now().date()
        if self.ultima_data is None:
            logging.info("Última data não definida, resetando contadores.")
            self.inicializar_contadores()
        elif self.ultima_data.date() < data_atual:
            logging.info("Novo dia detectado, resetando contadores.")
            self.inicializar_contadores()

    def salvar_contadores(self):
        dados = {
            "total_hd_encontrado": self.total_hd_encontrado,
            "total_matriculas_encontradas": self.total_matriculas_encontradas,
            "total_hd_nao_encontrado": self.total_hd_nao_encontrado,
            "total_mensagens_invalidas": self.total_mensagens_invalidas,
            "total_respostas_link": self.total_respostas_link,
            "total_matriculas_nao_encontrada": self.total_matriculas_nao_encontrada,
            "total_mesagens_respondidas": self.total_mesagens_respondidas,
            "ultima_data": str(datetime.now().date())
        }
        with open(self.arquivo_contadores, 'w', encoding='utf-8') as file:
            json.dump(dados, file, indent=4, ensure_ascii=False)

    def load_json_data_01_MATRICULA(self):
        try:
            dados = {}
            arquivos_csv = [
                'dados_matriculas/base_vcga.csv',
                'dados_matriculas/base_vcga2.csv',
                'dados_matriculas/base_vcga3.csv',
                'dados_matriculas/base_vcga4.csv',
                'dados_matriculas/base_vcga5.csv',
                'dados_matriculas/base_vcga6.csv',
                'dados_matriculas/base_vcga7.csv',
                'dados_matriculas/base_vcga8.csv',
                'dados_matriculas/base_vcga9.csv',
                'dados_matriculas/base_vcga10.csv',
            ]

            for arquivo in arquivos_csv:
                if not os.path.exists(arquivo):
                    continue

                with open(arquivo, encoding='utf-8') as file:
                    reader = csv.reader(file)
                    for linha in reader:
                        if len(linha) != 2:
                            continue

                        chave, json_str = linha
                        try:
                            dados[chave] = json.loads(json_str)
                        except json.JSONDecodeError as e:
                            logging.error(f"Erro ao decodificar JSON para chave {chave} no arquivo {arquivo}")

            return dados

        except Exception as exc:
            logging.error('Erro inesperado ao carregar os arquivos CSV', exc_info=exc)
            return None

    def montar_url_google_maps_da_01(self, matricula, source=None):
        try:
            data = self.load_json_data_01_MATRICULA()

            if data and matricula in data:
                info = data[matricula]
                latitude = info.get('Latitude') or info.get('latitude')
                longitude = info.get('Longitude') or info.get('longitude')

                # Verificar se as coordenadas existem e não estão vazias
                if not latitude or not longitude or str(latitude).strip() == "" or str(longitude).strip() == "":
                    logging.warning(f"Coordenadas ausentes ou vazias para matrícula {matricula}")
                    return None
                
                # Verificar se as coordenadas são válidas (não são 0 ou valores inválidos)
                try:
                    lat_float = float(latitude)
                    lng_float = float(longitude)
                    
                    if lat_float == 0.0 and lng_float == 0.0:
                        logging.warning(f"Coordenadas zeradas para matrícula {matricula}")
                        return None
                        
                except (ValueError, TypeError):
                    logging.warning(f"Coordenadas inválidas para matrícula {matricula}: lat={latitude}, lng={longitude}")
                    return None
                
                url = f"https://www.google.com/maps/search/?api=1&query={latitude},{longitude}"
                return url
            else:
                logging.error(f"A matrícula {matricula} não está presente nos dados.")
                return None

        except Exception as e:
            logging.error(f"Erro ao montar URL do Google Maps: {e}")
            return None

    def verificar_matricula(self, matricula_recebida, chat_id, sender_name):
        try:
            sender_clean = clean_text_for_log(sender_name)
            logging.info(f"Verificando matrícula: {matricula_recebida} para {sender_clean}")
            
            agora = datetime.now()
            saudacao = ""
            if 6 <= agora.hour < 12:
                saudacao = f"🅱🅾🅼 ​ 🅳🅸🅰! 🌤️"
            elif 12 <= agora.hour < 18:
                saudacao = f"🅱🅾🅰 ​ 🆃🅰🆁🅳🅴! ☀️"
            else:
                saudacao = f"🅱🅾🅰 ​ 🅽🅾🅸🆃🅴! 🌜"
            
            bases_vcga_matriculas = self.load_json_data_01_MATRICULA()
          
            if bases_vcga_matriculas and matricula_recebida in bases_vcga_matriculas:
                info = bases_vcga_matriculas[matricula_recebida]
                
                # Dados básicos da resposta
                data_formatada = datetime.now().strftime("%Y-%m-%d")
                hora_formatada = datetime.now().strftime("%H:%M:%S")
                
                message = f"""
🥳𝙎𝙚𝙟𝙖𝙢 𝙗𝙚𝙢 𝙫𝙞𝙣𝙙𝙤𝙨 𝙖𝙤 🤖𝙑𝘾𝙂𝘼-𝙇𝙚𝙞𝙩𝙪𝙧𝙖𝘼𝙀
                    
🤖{saudacao} 
👤{sender_name}

✅𝙈𝘼𝙏𝙍𝙄́𝘾𝙐𝙇𝘼 𝙀𝙉𝘾𝙊𝙉𝙏𝙍𝘼𝘿𝘼 𝙉𝙊 𝙎𝙄𝙎𝙏𝙀𝙈𝘼

➡️ 𝙈𝙖𝙩𝙧𝙞𝙘𝙪𝙡𝙖: {info.get('Matricula', 'Não informado')}
➡️ 𝘾𝙡𝙞𝙚𝙣𝙩𝙚: {info.get('Cliente', 'Não informado')}
➡️ 𝙀𝙣𝙙𝙚𝙧𝙚𝙘̧𝙤: {info.get('Endereço', 'Não informado')}
➡️ 𝘾𝙞𝙙𝙖𝙙𝙚: {info.get('Cidade', 'Não informado')}
➡️ 𝘽𝙖𝙞𝙧𝙧𝙤: {info.get('Bairro', 'Não informado')}
➡️ 𝘾𝙡𝙖𝙨𝙨𝙞𝙛𝙞𝙘𝙖𝙘̧𝙖̃𝙤: {info.get('Classificação', 'Não informado')}

🕐𝙃𝙤𝙧𝙖 𝙙𝙖 𝙍𝙚𝙨𝙥𝙤𝙨𝙩𝙖: {hora_formatada}
📆𝘿𝙖𝙩𝙖 𝙙𝙖 𝙍𝙚𝙨𝙥𝙤𝙨𝙩𝙖: {data_formatada}"""
                
                # Tentar obter URL do Google Maps
                url_maps = self.montar_url_google_maps_da_01(matricula_recebida, "BASE_VCGA_MATRICULAS")
                if url_maps:
                    message += f"\n📍𝙇𝙞𝙣𝙠 𝙥𝙖𝙧𝙖 𝙤 𝙂𝙤𝙤𝙜𝙡𝙚 𝙈𝙖𝙥𝙨: {url_maps}"
                    self.total_respostas_link += 1
                else:
                    message += f"\n⚠️ 𝘾𝙤𝙤𝙧𝙙𝙚𝙣𝙖𝙙𝙖𝙨 𝙣𝙖̃𝙤 𝙙𝙞𝙨𝙥𝙤𝙣𝙞́𝙫𝙚𝙞𝙨 𝙥𝙖𝙧𝙖 𝙚𝙨𝙩𝙖 𝙢𝙖𝙩𝙧𝙞́𝙘𝙪𝙡𝙖"
                
                self.responder_mensagem(chat_id, message)
                self.total_matriculas_encontradas += 1
                self.salvar_contadores()
                return True
            else:
                alerta_nao_encontrado = f"""
🥳𝙎𝙚𝙟𝙖𝙢 𝙗𝙚𝙢 𝙫𝙞𝙣𝙙𝙤𝙨 𝙖𝙤 🤖𝙑𝘾𝙂𝘼-𝙇𝙚𝙞𝙩𝙪𝙧𝙖𝘼𝙀
                    
🤖{saudacao} 
👤{sender_name}

➡️ 𝘼 𝙢𝙖𝙩𝙧𝙞́𝙘𝙪𝙡𝙖: ⚠️{matricula_recebida}
𝙉𝙤 𝙢𝙤𝙢𝙚𝙣𝙩𝙤 𝙣𝙖̃𝙤 𝙨𝙚 𝙚𝙣𝙘𝙤𝙣𝙩𝙧𝙖 𝙣𝙤 𝙗𝙖𝙣𝙘𝙤 𝙙𝙚 𝙙𝙖𝙙𝙤𝙨
                """
                self.responder_mensagem(chat_id, alerta_nao_encontrado)
                self.total_matriculas_nao_encontrada += 1
                self.salvar_contadores()
                return True
                
        except Exception as e:
            logging.error(f"Erro ao verificar matrícula: {e}")
            return False

    def verificar_hd(self, matricula_hd, chat_id, sender_name):
        try:
            sender_clean = clean_text_for_log(sender_name)
            logging.info(f"Verificando HD: {matricula_hd} para {sender_clean}")
            
            agora = datetime.now()
            saudacao = ""
            if 6 <= agora.hour < 12:
                saudacao = f"🅱🅾🅼 ​ 🅳🅸🅰! 🌤️"
            elif 12 <= agora.hour < 18:
                saudacao = f"🅱🅾🅰 ​ 🆃🅰🆁🅳🅴! ☀️"
            else:
                saudacao = f"🅱🅾🅰 ​ 🅽🅾🅸🆃🅴! 🌜"
            
            bases_vcga_hd = self.load_json_data_01_MATRICULA()

            if bases_vcga_hd and matricula_hd in bases_vcga_hd:
                info = bases_vcga_hd[matricula_hd]
                
                # Dados básicos da resposta
                data_formatada = datetime.now().strftime("%Y-%m-%d")
                hora_formatada = datetime.now().strftime("%H:%M:%S")
                
                message = f"""
🥳𝙎𝙚𝙟𝙖𝙢 𝙗𝙚𝙢 𝙫𝙞𝙣𝙙𝙤𝙨 𝙖𝙤 🤖𝙑𝘾𝙂𝘼-𝙇𝙚𝙞𝙩𝙪𝙧𝙖𝘼𝙀

🤖{saudacao} 
👤{sender_name}

✅𝙃𝘿 𝙀𝙉𝘾𝙊𝙉𝙏𝙍𝘼𝘿𝙊 𝙉𝙊 𝙎𝙄𝙎𝙏𝙀𝙈𝘼

➡️ 𝙄𝙣𝙛𝙤𝙧𝙢𝙖𝙘̧𝙤̃𝙚𝙨 𝙙𝙤 𝙃𝘿: {matricula_hd}
➡️ 𝙈𝙖𝙩𝙧𝙞𝙘𝙪𝙡𝙖: {info.get('Matricula', 'Não informado')}
➡️ 𝘾𝙡𝙞𝙚𝙣𝙩𝙚: {info.get('Cliente', 'Não informado')}
➡️ 𝙀𝙣𝙙𝙚𝙧𝙚𝙘̧𝙤: {info.get('Endereço', 'Não informado')}
➡️ 𝘾𝙞𝙙𝙖𝙙𝙚: {info.get('Cidade', 'Não informado')}
➡️ 𝘽𝙖𝙞𝙧𝙧𝙤: {info.get('Bairro', 'Não informado')}
➡️ 𝘾𝙡𝙖𝙨𝙨𝙞𝙛𝙞𝙘𝙖𝙘̧𝙖̃𝙤: {info.get('Classificação', 'Não informado')}

🕐𝙃𝙤𝙧𝙖 𝙙𝙖 𝙍𝙚𝙨𝙥𝙤𝙨𝙩𝙖: {hora_formatada}
📆𝘿𝙖𝙩𝙖 𝙙𝙖 𝙍𝙚𝙨𝙥𝙤𝙨𝙩𝙖: {data_formatada}"""
                
                # Tentar obter URL do Google Maps
                url_maps = self.montar_url_google_maps_da_01(matricula_hd, "BASE_VCGA_HD")
                if url_maps:
                    message += f"\n📍𝙇𝙞𝙣𝙠 𝙥𝙖𝙧𝙖 𝙤 𝙂𝙤𝙤𝙜𝙡𝙚 𝙈𝙖𝙥𝙨: {url_maps}"
                    self.total_respostas_link += 1
                else:
                    message += f"\n⚠️ 𝘾𝙤𝙤𝙧𝙙𝙚𝙣𝙖𝙙𝙖𝙨 𝙣𝙖̃𝙤 𝙙𝙞𝙨𝙥𝙤𝙣𝙞́𝙫𝙚𝙞𝙨 𝙥𝙖𝙧𝙖 𝙚𝙨𝙩𝙚 𝙃𝘿"
                
                self.responder_mensagem(chat_id, message)
                self.total_hd_encontrado += 1
                self.salvar_contadores()
                return True
            else:
                alerta_nao_encontrado = f"""
🥳𝙎𝙚𝙟𝙖𝙢 𝙗𝙚𝙢 𝙫𝙞𝙣𝙙𝙤𝙨 𝙖𝙤 🤖𝙑𝘾𝙂𝘼-𝙇𝙚𝙞𝙩𝙪𝙧𝙖𝘼𝙀
                    
🤖{saudacao} 
👤{sender_name}

➡️ 𝙊 𝙃𝘿: ⚠️{matricula_hd}
𝙉𝙤 𝙢𝙤𝙢𝙚𝙣𝙩𝙤 𝙣𝙖̃𝙤 𝙨𝙚 𝙚𝙣𝙘𝙤𝙣𝙩𝙧𝙖 𝙣𝙤 𝙗𝙖𝙣𝙘𝙤 𝙙𝙚 𝙙𝙖𝙙𝙤𝙨
                """
                self.responder_mensagem(chat_id, alerta_nao_encontrado)
                self.total_hd_nao_encontrado += 1
                self.salvar_contadores()
                return True
                
        except Exception as e:
            logging.error(f"Erro ao verificar HD: {e}")
            return False

    def responder_mensagem(self, chat_id, mensagem):
        max_retries = 3
        retry_delay = 5
        attempt = 0

        while attempt < max_retries:
            try:
                url = f'{self.base_url}/send-message'
                payload = {
                    'number': chat_id.split('@')[0] if '@' in chat_id else chat_id,
                    'message': mensagem
                }
                response = requests.post(url, json=payload)

                if response.status_code == 200:
                    logging.info(f"Mensagem enviada para {chat_id}")
                    self.total_mesagens_respondidas += 1
                    self.salvar_contadores()
                    return True
                elif response.status_code == 500:
                    logging.warning(f"Erro 500 ao enviar mensagem para {chat_id} - Tentativa {attempt + 1} de {max_retries}")
                    attempt += 1
                    time.sleep(retry_delay)
                    return
                else:
                    logging.error(f"Erro ao enviar mensagem para {chat_id}: {response.status_code}")
                    return False

            except Exception as e:
                logging.error(f"Exceção ao enviar mensagem: {e}")
                attempt += 1
                time.sleep(retry_delay)
                
        return False

    def as_msg_enviadas(self, respost_chat, mensagem_texto, sender_name):
        if respost_chat == "explicaar_sistema":
            return """
🥳𝙎𝙚𝙟𝙖𝙢 𝙗𝙚𝙢 𝙫𝙞𝙣𝙙𝙤𝙨 𝙖𝙤 🤖𝙑𝘾𝙂𝘼-𝙇𝙚𝙞𝙩𝙪𝙧𝙖𝘼𝙀

👋 Olá! Eu sou um assistente virtual projetado para ajudar você com localização e informações detalhadas sobre matrículas ou HDs digitados.

🔎𝘿𝙞𝙜𝙞𝙩𝙚 𝙤𝙨 𝟵 𝙣𝙪́𝙢𝙚𝙧𝙤𝙨 𝙘𝙤𝙣𝙛𝙤𝙧𝙢𝙚 𝙖 𝙢𝙖𝙩𝙧𝙞́𝙘𝙪𝙡𝙖 𝙚𝙭:𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵

🔎𝙋𝙖𝙧𝙖 𝙨𝙤𝙡𝙞𝙘𝙞𝙩𝙖𝙧 𝙥𝙚𝙨𝙦𝙪𝙞𝙨𝙖 𝙥𝙤𝙧 𝙃𝘿 𝙪𝙨𝙚 /. 𝙚𝙭:/𝙔𝟮𝟭𝘾𝟬𝟬𝟬𝟬𝟬𝟬

Desenvolvido por Alisson Cardozo Varela

✍️ASS: ALISSON CARDOZO
        """
                
        elif respost_chat == "mensagem_erradas":
            agora = datetime.now()
            saudacao = ""
            if 6 <= agora.hour < 12:
                saudacao = f"🅱🅾🅼 ​ 🅳🅸🅰! 🌤️"
            elif 12 <= agora.hour < 18:
                saudacao = f"🅱🅾🅰 ​ 🆃🅰🆁🅳🅴! ☀️"
            else:
                saudacao = f"🅱🅾🅰 ​ 🅽🅾🅸🆃🅴! 🌜"

            return f"""
🥳𝙎𝙚𝙟𝙖𝙢 𝙗𝙚𝙢 𝙫𝙞𝙣𝙙𝙤𝙨 𝙖𝙤 🤖𝙑𝘾𝙂𝘼-𝙇𝙚𝙞𝙩𝙪𝙧𝙖𝘼𝙀

🤖{saudacao} 
👤{sender_name}

🚫𝙑𝙤𝙘𝙚̂ 𝙙𝙞𝙜𝙞𝙩𝙤𝙪: {mensagem_texto} 

🔎𝘿𝙞𝙜𝙞𝙩𝙚 𝙤𝙨 𝟵 𝙣𝙪́𝙢𝙚𝙧𝙤𝙨 𝙘𝙤𝙣𝙛𝙤𝙧𝙢𝙚 𝙖 𝙢𝙖𝙩𝙧𝙞́𝙘𝙪𝙡𝙖 𝙚𝙭:𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵

🔎𝙋𝙖𝙧𝙖 𝙨𝙤𝙡𝙞𝙘𝙞𝙩𝙖𝙧 𝙥𝙚𝙨𝙦𝙪𝙞𝙨𝙖 𝙥𝙤𝙧 𝙃𝘿 𝙪𝙨𝙚 /. 𝙚𝙭:/𝙔𝟮𝟭𝘾𝟬𝟬𝟬𝟬𝟬𝟬

Desenvolvido por Alisson Cardozo Varela

✍️ASS: ALISSON CARDOZO
    """
        elif respost_chat == "mensagem_link":
            agora = datetime.now()
            saudacao = ""
            if 6 <= agora.hour < 12:
                saudacao = f"🅱🅾🅼 ​ 🅳🅸🅰! 🌤️"
            elif 12 <= agora.hour < 18:
                saudacao = f"🅱🅾🅰 ​ 🆃🅰🆁🅳🅴! ☀️"
            else:
                saudacao = f"🅱🅾🅰 ​ 🅽🅾🅸🆃🅴! 🌜"

            return f"""
🥳𝙎𝙚𝙟𝙖𝙢 𝙗𝙚𝙢 𝙫𝙞𝙣𝙙𝙤𝙨 𝙖𝙤 🤖𝙑𝘾𝙂𝘼-𝙇𝙚𝙞𝙩𝙪𝙧𝙖𝘼𝙀

🤖{saudacao} 
👤{sender_name}

🔎𝙎𝙚𝙜𝙪𝙚 𝙤𝙨 𝙡𝙞𝙣𝙠𝙨 𝙥𝙖𝙧𝙖 𝙢𝙚𝙡𝙝𝙤𝙧𝙚𝙨 𝙖𝙩𝙚𝙣𝙙𝙞𝙢𝙚𝙣𝙩𝙤𝙨.

🔗{self.msg_links[0]}

🔗{self.msg_links[1]}

🔗{self.msg_links[2]}

🔗{self.msg_links[3]}

🔗{self.msg_links[4]}

🔗{self.msg_links[5]}

🔗{self.msg_links[6]}

✍️ASS: ALISSON CARDOZO
"""

        return "Mensagem não reconhecida"

    def processar_mensagens(self):
        global is_bot_running

        while is_bot_running:
            try:
                schedule.run_pending()
                
                response = requests.get(f'{self.base_url}/chats', timeout=10)
                
                if response.status_code == 200:
                    chats = response.json()
                    
                    for chat in chats:
                        is_group = chat.get('isGroup', False)
                        if is_group:
                            continue
                            
                        unread_count = chat.get('unreadCount', 0)
                        last_message = chat.get('lastMessage', {})
                        
                        if unread_count > 0 and last_message:
                            mensagem_texto = last_message.get('body', '').strip()
                            sender_name = chat.get('name', 'Usuário Desconhecido')
                            chat_id = chat['id']['_serialized']
                            
                            # Log com texto limpo
                            sender_clean = clean_text_for_log(sender_name)
                            message_clean = clean_text_for_log(mensagem_texto)
                            logging.info(f"Processando mensagem de {sender_clean}: {message_clean}")
                            
                            # Verificar se é matrícula (9 dígitos)
                            if mensagem_texto.isdigit() and len(mensagem_texto) == 9:
                                logging.info(f"Verificando matrícula: {mensagem_texto}")
                                self.verificar_matricula(mensagem_texto, chat_id, sender_name)
                            
                            elif mensagem_texto.upper().startswith("LINK"):
                                resposta = self.as_msg_enviadas("mensagem_link", mensagem_texto, sender_name)
                                self.responder_mensagem(chat_id, resposta)
                                self.total_respostas_link += 1
                                self.salvar_contadores()
                                
                            # Verificar se é HD (começa com /)
                            elif mensagem_texto.startswith("/"):
                                HD_EM_BUSCAR = mensagem_texto[1:].upper()
                                logging.info(f"Verificando HD: {HD_EM_BUSCAR}")
                                self.verificar_hd(HD_EM_BUSCAR, chat_id, sender_name)
                            
                            # Verificar saudações
                            elif any(mensagem_texto.lower().startswith(prefix.lower()) for prefix in self.digitdocliente):
                                logging.info(f"Enviando explicação do sistema para: {sender_clean}")
                                resposta = self.as_msg_enviadas("explicaar_sistema", mensagem_texto, sender_name)
                                self.responder_mensagem(chat_id, resposta)
                                self.total_mensagens_invalidas += 1
                                self.salvar_contadores()
                            
                            # Mensagem não reconhecida
                            else:
                                logging.info(f"Mensagem não reconhecida de: {sender_clean}")
                                resposta = self.as_msg_enviadas("mensagem_erradas", mensagem_texto, sender_name)
                                self.responder_mensagem(chat_id, resposta)
                                self.total_mensagens_invalidas += 1
                                self.salvar_contadores()
            
                time.sleep(1)
                
            except requests.exceptions.RequestException as e:
                logging.error(f"Erro de conexão com o servidor WhatsApp: {e}")
                time.sleep(5)
                
            except Exception as e:
                logging.error(f"Erro ao processar mensagens: {e}")
                time.sleep(2)

    def finalizar(self):
        global is_bot_running
        logging.info("Finalizando o bot")
        is_bot_running = False

@bot_bp.route('/start', methods=['POST'])
def start_bot():
    global bot_thread, is_bot_running
    
    # Verificar se o servidor WhatsApp está rodando
    from modules.whatsapp_manager import is_server_running
    
    if not is_server_running:
        return jsonify({'success': False, 'message': 'Servidor WhatsApp não está rodando'})
    
    if not is_bot_running:
        try:
            response = requests.get('http://localhost:3000/status')
            if response.status_code != 200:
                return jsonify({'success': False, 'message': 'WhatsApp não está conectado'})
            
            bot = ChatBot()
            is_bot_running = True
            bot_thread = threading.Thread(target=bot.processar_mensagens)
            bot_thread.daemon = True
            bot_thread.start()
            
            return jsonify({'success': True})
            
        except Exception as e:
            logging.error(f"Erro ao iniciar bot: {e}")
            return jsonify({'success': False, 'message': str(e)})
    
    return jsonify({'success': True, 'message': 'Bot já está rodando'})

@bot_bp.route('/stop', methods=['POST'])
def stop_bot():
    global is_bot_running
    
    if is_bot_running:
        is_bot_running = False
        if bot_thread:
            bot_thread.join(timeout=5)
        return jsonify({'success': True})
    
    return jsonify({'success': True, 'message': 'Bot não está rodando'})

@bot_bp.route('/status')
def status():
    return jsonify(get_bot_status())
