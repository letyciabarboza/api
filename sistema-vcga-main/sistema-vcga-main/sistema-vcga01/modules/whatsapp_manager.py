from flask import Blueprint, request, jsonify
import subprocess
import threading
import requests
import time
import logging
import os
import shutil
import psutil

whatsapp_bp = Blueprint('whatsapp', __name__)

# Variáveis globais para o sistema único
node_process = None
is_server_running = False
whatsapp_status = "Offline"
qr_code_data = None

# Caminho para o arquivo JavaScript
JS_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "whatsapp-server.js")

def get_whatsapp_status():
    """Retorna o status do WhatsApp"""
    return {
        'status': whatsapp_status,
        'server_running': is_server_running,
        'has_qr': qr_code_data is not None
    }

def force_kill_node_processes():
    """Força o encerramento de todos os processos Node.js relacionados"""
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['name'] and 'node' in proc.info['name'].lower():
                    cmdline = proc.info['cmdline']
                    if cmdline and any('whatsapp' in str(cmd).lower() for cmd in cmdline):
                        logging.info(f"Encerrando processo Node.js: {proc.info['pid']}")
                        proc.kill()
                        proc.wait(timeout=3)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    except Exception as e:
        logging.error(f"Erro ao encerrar processos Node.js: {e}")

def clear_whatsapp_session():
    """Remove os dados de sessão do WhatsApp com força"""
    try:
        session_path = ".wwebjs_auth"
        
        # Tentar remover normalmente primeiro
        if os.path.exists(session_path):
            try:
                shutil.rmtree(session_path)
                logging.info("Sessão do WhatsApp removida com sucesso")
                return True
            except PermissionError as e:
                logging.warning(f"Erro de permissão ao remover sessão: {e}")
                
                # Forçar encerramento de processos Node.js
                force_kill_node_processes()
                time.sleep(2)
                
                # Tentar novamente após encerrar processos
                try:
                    shutil.rmtree(session_path)
                    logging.info("Sessão do WhatsApp removida após encerrar processos")
                    return True
                except Exception as e2:
                    logging.error(f"Erro persistente ao remover sessão: {e2}")
                    
                    # Última tentativa: remover arquivos individualmente
                    return force_remove_session_files(session_path)
            except Exception as e:
                logging.error(f"Erro inesperado ao remover sessão: {e}")
                return force_remove_session_files(session_path)
        else:
            logging.info("Pasta de sessão não encontrada")
            return True
            
    except Exception as e:
        logging.error(f"Erro geral ao remover sessão do WhatsApp: {e}")
        return False

def force_remove_session_files(session_path):
    """Remove arquivos de sessão individualmente com força"""
    try:
        import stat
        
        def handle_remove_readonly(func, path, exc):
            """Manipula arquivos somente leitura"""
            if os.path.exists(path):
                os.chmod(path, stat.S_IWRITE)
                func(path)
        
        if os.path.exists(session_path):
            # Alterar permissões recursivamente
            for root, dirs, files in os.walk(session_path):
                for d in dirs:
                    os.chmod(os.path.join(root, d), stat.S_IWRITE)
                for f in files:
                    file_path = os.path.join(root, f)
                    if os.path.exists(file_path):
                        os.chmod(file_path, stat.S_IWRITE)
            
            # Tentar remover com manipulador de erro
            shutil.rmtree(session_path, onerror=handle_remove_readonly)
            
            # Verificar se foi removido
            if not os.path.exists(session_path):
                logging.info("Sessão removida com força")
                return True
            else:
                logging.error("Falha ao remover sessão mesmo com força")
                return False
        else:
            return True
            
    except Exception as e:
        logging.error(f"Erro ao forçar remoção de arquivos: {e}")
        return False

def check_node_installed():
    """Verifica se o Node.js está instalado"""
    try:
        result = subprocess.run(['node', '--version'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            logging.info(f"Node.js instalado: {result.stdout.strip()}")
            return True
        else:
            logging.error("Node.js não está instalado ou não está no PATH")
            return False
    except Exception as e:
        logging.error(f"Erro ao verificar Node.js: {e}")
        return False

def check_npm_packages():
    """Verifica se os pacotes npm necessários estão instalados"""
    required_packages = ['whatsapp-web.js', 'express', 'qrcode']
    missing_packages = []
    
    for package in required_packages:
        try:
            # Tenta importar o pacote via Node.js
            result = subprocess.run(
                ['node', '-e', f"try {{ require('{package}'); console.log('ok'); }} catch(e) {{ console.log('error'); }}"],
                capture_output=True, text=True
            )
            
            if 'error' in result.stdout:
                missing_packages.append(package)
                logging.warning(f"Pacote {package} não está instalado")
            else:
                logging.info(f"Pacote {package} está instalado")
                
        except Exception as e:
            logging.error(f"Erro ao verificar pacote {package}: {e}")
            missing_packages.append(package)
    
    return missing_packages

def install_npm_packages(packages):
    """Instala pacotes npm necessários"""
    if not packages:
        return True
        
    try:
        cmd = ['npm', 'install'] + packages
        logging.info(f"Instalando pacotes: {' '.join(packages)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            logging.info("Pacotes instalados com sucesso")
            return True
        else:
            logging.error(f"Erro ao instalar pacotes: {result.stderr}")
            return False
    except Exception as e:
        logging.error(f"Erro ao executar npm install: {e}")
        return False

def create_js_file():
    """Cria o arquivo JavaScript se não existir"""
    # Verificar se o arquivo já existe
    if os.path.exists(JS_FILE_PATH):
        logging.info(f"Arquivo JavaScript já existe: {JS_FILE_PATH}")
        return True
        
    try:
        # Obter o diretório do arquivo
        js_dir = os.path.dirname(JS_FILE_PATH)
        
        # Criar o diretório se não existir
        if not os.path.exists(js_dir):
            os.makedirs(js_dir)
            
        # Escrever o código no arquivo
        with open(JS_FILE_PATH, 'w') as f:
            f.write("""
const { Client, LocalAuth, MessageMedia } = require('whatsapp-web.js');
const express = require('express');
const qrcode = require('qrcode');
const app = express();
app.use(express.json());

let requestQueue = [];
let isProcessing = false;
let currentQRCode = null;

const restartClient = () => {
    console.log('Reinicializando o cliente...');
    currentQRCode = null;
    client.destroy();
    setTimeout(() => {
        client.initialize();
        console.log('Cliente reinicializado.');
    }, 5000);
}

let client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: {
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox'],
        timeout: 60000
    }
});

client.on('qr', async (qr) => {
    console.log('QR Code gerado');
    try {
        currentQRCode = await qrcode.toDataURL(qr);
        console.log('QR Code convertido para base64');
    } catch (err) {
        console.error('Erro ao gerar QR code:', err);
    }
});

client.on('ready', () => {
    console.log('WhatsApp Web Client está pronto!');
    currentQRCode = null;
    
    while (requestQueue.length > 0) {
        const { req, res, action } = requestQueue.shift();
        requestQueue.push({ req, res, action });
        processQueue();
    }
});

app.get('/qr', (req, res) => {
    if (currentQRCode) {
        res.json({ qr: currentQRCode });
    } else {
        res.status(404).json({ error: 'QR Code não disponível' });
    }
});

const processQueue = () => {
    if (isProcessing || requestQueue.length === 0) return;

    isProcessing = true;
    const { req, res, action } = requestQueue.shift();

    action(req, res).finally(() => {
        setTimeout(() => {
            isProcessing = false;
            processQueue();
        }, 1000);
    });
};

app.post('/send-message', (req, res) => {
    const action = async (req, res, attempt = 1) => {
        if (!client.info) {
            return res.status(500).send({ status: 'error', message: 'Cliente não está conectado' });
        }

        const { number, message } = req.body;
        const chatId = `${number}@c.us`;

        try {
            await client.sendMessage(chatId, message);
            res.status(200).send({ status: 'success', message: 'Mensagem enviada!' });
        } catch (error) {
            if (attempt < 3) {
                console.log(`Erro ao enviar mensagem. Tentativa ${attempt} de 3.`);
                await action(req, res, attempt + 1);
            } else {
                res.status(500).send({ status: 'error', message: error.toString() });
            }
        }
    };

    requestQueue.push({ req, res, action });
    processQueue();
});

app.get('/status', (req, res) => {
    const info = client.info;
    if (info) {
        res.status(200).send({
            status: 'connected',
            pushname: info.pushname,
            number: info.me.user,
            platform: info.platform,
            hasQR: false
        });
    } else {
        res.status(500).send({ 
            status: 'disconnected', 
            message: 'Cliente não está conectado',
            hasQR: currentQRCode !== null
        });
    }
});

app.get('/chats', async (req, res) => {
    try {
        const chats = await client.getChats();
        res.status(200).json(chats);
    } catch (error) {
        res.status(500).send({ status: 'error', message: error.toString() });
    }
});

app.post('/shutdown', (req, res) => {
    console.log('Desligando o servidor...');
    res.status(200).send({ status: 'success', message: 'Servidor desligado.' });
    process.exit();
});

// Adicionar rota para verificar se o servidor está rodando
app.get('/ping', (req, res) => {
    res.status(200).send({ status: 'ok', message: 'Servidor está rodando' });
});

client.initialize();

app.listen(3000, () => {
    console.log('API está rodando em http://localhost:3000');
});

client.on('error', (error) => {
    console.error('Erro no cliente WhatsApp:', error);
    restartClient();
});

client.on('disconnected', (reason) => {
    console.log('Cliente desconectado:', reason);
    currentQRCode = null;
});
""")
        logging.info(f"Arquivo JavaScript criado: {JS_FILE_PATH}")
        return True
    except Exception as e:
        logging.error(f"Erro ao criar arquivo JavaScript: {e}")
        return False

def start_node_server():
    global node_process, is_server_running, whatsapp_status
    
    try:
        # Verificar se o Node.js está instalado
        if not check_node_installed():
            return False
            
        # Verificar e instalar pacotes npm necessários
        missing_packages = check_npm_packages()
        if missing_packages:
            if not install_npm_packages(missing_packages):
                return False
                
        # Criar arquivo JavaScript se não existir
        if not create_js_file():
            return False
            
        # Iniciar o servidor Node.js
        logging.info(f"Iniciando servidor Node.js com arquivo: {JS_FILE_PATH}")
        node_process = subprocess.Popen(['node', JS_FILE_PATH], 
                                      stdout=subprocess.PIPE, 
                                      stderr=subprocess.PIPE,
                                      text=True,
                                      bufsize=1,
                                      universal_newlines=True)
        
        is_server_running = True
        whatsapp_status = "Iniciando"
        
        threading.Thread(target=read_node_output, daemon=True).start()
        
        # Aguardar um pouco para o servidor iniciar
        time.sleep(5)
        
        # Verificar se o servidor está rodando
        try:
            response = requests.get('http://localhost:3000/ping', timeout=5)
            if response.status_code == 200:
                logging.info("Servidor Node.js iniciado com sucesso")
                return True
            else:
                logging.error(f"Servidor respondeu com status: {response.status_code}")
                return False
        except requests.exceptions.ConnectionError:
            logging.error("Não foi possível conectar ao servidor Node.js")
            
            # Verificar se houve erro no processo
            if node_process.poll() is not None:
                stderr = node_process.stderr.read()
                logging.error(f"Erro no servidor Node.js: {stderr}")
                
            return False
        except Exception as e:
            logging.error(f"Erro ao verificar servidor: {e}")
            return False
            
    except Exception as e:
        logging.error(f"Erro ao iniciar servidor Node.js: {e}")
        is_server_running = False
        return False

def read_node_output():
    global node_process, whatsapp_status, qr_code_data
    
    for line in iter(node_process.stdout.readline, ''):
        logging.info(f"Node.js: {line.strip()}")
        
        # Corrigir detecção de status - usar texto em português
        if "WhatsApp Web Client está pronto" in line or "WhatsApp Web Client estÃ¡ pronto" in line:
            whatsapp_status = "Conectado"
            qr_code_data = None
            logging.info("Status atualizado para: Conectado")
        elif "QR Code gerado" in line:
            whatsapp_status = "Aguardando QR Code"
            logging.info("Status atualizado para: Aguardando QR Code")
            try:
                time.sleep(1)
                response = requests.get('http://localhost:3000/qr')
                if response.status_code == 200:
                    qr_data = response.json()
                    qr_code_data = qr_data.get('qr')
                    logging.info("QR Code obtido com sucesso")
            except Exception as e:
                logging.error(f"Erro ao obter QR code: {e}")
        elif "Cliente desconectado" in line:
            whatsapp_status = "Offline"
            qr_code_data = None
            logging.info("Status atualizado para: Offline")
            
    # Se chegou aqui, o processo terminou
    stderr = node_process.stderr.read()
    if stderr:
        logging.error(f"Erro no servidor Node.js: {stderr}")
        
    logging.info("Saída do Node.js finalizada")

# Resto do código permanece igual...

def stop_node_server():
    global node_process, is_server_running, whatsapp_status
    
    if node_process and is_server_running:
        try:
            # Tentar parar graciosamente
            requests.post('http://localhost:3000/shutdown', timeout=5)
            node_process.wait(timeout=5)
        except:
            try:
                # Forçar encerramento
                node_process.terminate()
                node_process.wait(timeout=5)
            except:
                try:
                    # Matar processo
                    node_process.kill()
                    node_process.wait(timeout=3)
                except:
                    pass
        
        # Forçar encerramento de processos Node.js restantes
        force_kill_node_processes()
        
        is_server_running = False
        whatsapp_status = "Offline"
        qr_code_data = None
        return True
    
    return False

@whatsapp_bp.route('/start-server', methods=['POST'])
def start_server():
    if not is_server_running:
        success = start_node_server()
        return jsonify({'success': success})
    
    return jsonify({'success': True, 'message': 'Servidor já está rodando'})

@whatsapp_bp.route('/stop-server', methods=['POST'])
def stop_server():
    success = stop_node_server()
    return jsonify({'success': success})

@whatsapp_bp.route('/clear-session', methods=['POST'])
def clear_session():
    """Remove os dados de sessão do WhatsApp para permitir nova conexão"""
    global whatsapp_status, qr_code_data
    
    try:
        logging.info("Iniciando limpeza de sessão do WhatsApp")
        
        # Parar o servidor se estiver rodando
        if is_server_running:
            logging.info("Parando servidor WhatsApp...")
            stop_node_server()
            time.sleep(3)  # Aguardar mais tempo para garantir que parou
        
        # Forçar encerramento de processos Node.js
        logging.info("Encerrando processos Node.js...")
        force_kill_node_processes()
        time.sleep(2)
        
        # Limpar a sessão
        logging.info("Removendo arquivos de sessão...")
        success = clear_whatsapp_session()
        
        if success:
            whatsapp_status = "Offline"
            qr_code_data = None
            
            # Verificar se a pasta foi realmente removida
            if not os.path.exists(".wwebjs_auth"):
                logging.info("Sessão removida com sucesso - pasta não existe mais")
                return jsonify({
                    'success': True, 
                    'message': 'Sessão do WhatsApp removida com sucesso! Você pode conectar um novo número.'
                })
            else:
                logging.error("Pasta ainda existe após tentativa de remoção")
                return jsonify({
                    'success': False, 
                    'message': 'Erro: A pasta de sessão ainda existe. Tente novamente ou remova manualmente.'
                })
        else:
            return jsonify({
                'success': False, 
                'message': 'Erro ao remover sessão do WhatsApp. Verifique os logs para mais detalhes.'
            })
            
    except Exception as e:
        logging.error(f"Erro geral na limpeza de sessão: {e}")
        return jsonify({
            'success': False, 
            'message': f'Erro inesperado: {str(e)}'
        })

@whatsapp_bp.route('/status')
def status():
    return jsonify(get_whatsapp_status())

@whatsapp_bp.route('/qr')
def get_qr():
    global qr_code_data
    
    if qr_code_data:
        return jsonify({'qr': qr_code_data})
    else:
        try:
            response = requests.get('http://localhost:3000/qr')
            if response.status_code == 200:
                qr_data = response.json()
                qr_code_data = qr_data.get('qr')
                return jsonify({'qr': qr_code_data})
        except:
            pass
        
        return jsonify({'qr': None})

@whatsapp_bp.route('/test-message', methods=['POST'])
def test_message():
    """Envia uma mensagem de teste para o número especificado"""
    if not is_server_running:
        return jsonify({
            'success': False,
            'message': 'O servidor WhatsApp não está rodando'
        })
        
    try:
        data = request.json
        number = data.get('number', '')
        
        # Validar número
        if not number or not number.isdigit():
            return jsonify({
                'success': False,
                'message': 'Número inválido. Use apenas dígitos.'
            })
            
        # Enviar mensagem de teste
        message = """
🤖 *Mensagem de Teste - VCGA*

✅ Esta é uma mensagem de teste do sistema VCGA Bot.
📱 Seu sistema está funcionando corretamente!

📆 Data: {}
⏰ Hora: {}
""".format(
            time.strftime("%d/%m/%Y"),
            time.strftime("%H:%M:%S")
        )
        
        # Formatar número para WhatsApp (adicionar código do país se não tiver)
        if len(number) <= 11:  # Número brasileiro sem código do país
            formatted_number = "55" + number
        else:
            formatted_number = number
            
        # Chamar API do WhatsApp
        url = 'http://localhost:3000/send-message' #f'{base_url}/send-message'
        payload = {
            'number': formatted_number,
            'message': message
        }
        
        logging.info(f"Enviando mensagem de teste para {formatted_number}")
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            logging.info(f"Mensagem de teste enviada com sucesso para {formatted_number}")
            return jsonify({
                'success': True,
                'message': 'Mensagem enviada com sucesso!'
            })
        else:
            error_msg = f"Erro ao enviar mensagem: {response.status_code}"
            logging.error(error_msg)
            return jsonify({
                'success': False,
                'message': error_msg
            })
            
    except Exception as e:
        error_msg = f"Erro ao enviar mensagem de teste: {str(e)}"
        logging.error(error_msg)
        return jsonify({
            'success': False,
            'message': error_msg
        })
