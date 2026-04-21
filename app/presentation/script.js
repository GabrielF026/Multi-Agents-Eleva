// Elementos
const chatMessages = document.getElementById('chat-messages');
const chatInput = document.getElementById('chat-input');
const btnSend = document.getElementById('btn-send');
const btnReset = document.getElementById('btn-reset');

const dbgGoal = document.getElementById('dbg-goal');
const dbgScore = document.getElementById('dbg-score');

// Estado
let history = [];
let currentGoal = null;

// Envio de Evento
btnSend.addEventListener('click', sendMessage);
chatInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && chatInput.value.trim() !== '') {
        sendMessage();
    }
});

btnReset.addEventListener('click', () => {
    // Reset visual e estado
    chatMessages.innerHTML = `
        <div class="message ai-message fade-in">
            <div class="bubble">
                Olá! Sou o agente virtual da Eleva. Para qual produto de crédito ou renegociação você busca simulação hoje?
            </div>
            <span class="timestamp">Agora</span>
        </div>
    `;
    history = [];
    currentGoal = null;
    updateDebug("AGUARDANDO...", "badge-neutral", "N/A", "badge-neutral");
});

function formatTime() {
    const now = new Date();
    return now.getHours().toString().padStart(2, '0') + ':' + now.getMinutes().toString().padStart(2, '0');
}

function appendMessage(text, isAi = false) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${isAi ? 'ai-message' : 'user-message'}`;
    
    // Tratamento de quebras de linha para a UI
    const formattedText = text.replace(/\n/g, '<br>');
    
    msgDiv.innerHTML = `
        <div class="bubble">${formattedText}</div>
        <span class="timestamp">${formatTime()}</span>
    `;
    
    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function showTypingIndicator() {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ai-message`;
    msgDiv.id = 'typing-indicator-container';
    
    msgDiv.innerHTML = `
        <div class="bubble" style="padding: 0.8rem 1.25rem;">
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        </div>
    `;
    
    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function hideTypingIndicator() {
    const indicator = document.getElementById('typing-indicator-container');
    if (indicator) {
        indicator.remove();
    }
}

function updateDebug(goal, goalClass, score, scoreClass) {
    dbgGoal.textContent = goal || 'N/A';
    dbgGoal.className = `value badge ${goalClass}`;
    
    dbgScore.textContent = score || 'N/A';
    dbgScore.className = `value badge ${scoreClass}`;
}

function getScoreColorClass(score) {
    if (!score) return 'badge-neutral';
    const s = score.toUpperCase();
    if (s === 'HOT') return 'badge-red';
    if (s === 'WARM') return 'badge-amber';
    if (s === 'COLD') return 'badge-green'; // Usando green para cold/tranquilo ou blue, mas criamos classes antes
    return 'badge-blue';
}

async function sendMessage() {
    const text = chatInput.value.trim();
    if (!text) return;

    // 1. Renderiza User
    appendMessage(text, false);
    chatInput.value = '';

    // 2. Cria payload e atualiza history temporario
    const payload = {
        message: text,
        history: history,
        current_goal: currentGoal,
        is_repeated: false
    };

    // Atualiza history local para os próximos turnos (assumir q enviamos com sucesso)
    history.push({ role: 'user', content: text });

    // 3. Mostra "Digitando..."
    showTypingIndicator();

    try {
        // Obter do mesmo host atual (pois serviremos pelo FastAPI)
        // const baseUrl = window.location.origin; 
        // Usamos localhost explícito se for arquivo abeto
        const targetUrl = window.location.protocol.includes('file') 
            ? 'http://localhost:8000/chat' 
            : `${window.location.origin}/chat`;

        const response = await fetch(targetUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            throw new Error(`Erro HTTTP: ${response.status}`);
        }

        const data = await response.json();
        hideTypingIndicator();

        // Extrai dados da resposta diretamente do modelo retornado pelo FastAPI
        const replyText = data.sdr_response || "Comunicação falhou.";
        const g = data.classification?.goal;
        const s = data.lead_score?.score;

        // Renderiza AI
        appendMessage(replyText, true);

        // Atualiza History
        history.push({ role: 'assistant', content: replyText });
        
        // Mantem goal caso detectado
        if (g && g !== 'UNKNOWN' && g !== 'OUT_OF_DOMAIN') {
            currentGoal = g;
        }

        // Atualiza UI de Debug
        updateDebug(
            g, 
            g && g !== 'UNKNOWN' ? 'badge-blue' : 'badge-neutral',
            s,
            getScoreColorClass(s)
        );

    } catch (error) {
        console.error("Chat API falhou:", error);
        hideTypingIndicator();
        appendMessage("⚠️ Houve um erro interno de conexão com o Agente Eleva. O servidor está rodando?", true);
    }
}
