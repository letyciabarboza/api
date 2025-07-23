
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
