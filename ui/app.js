/**
 * OllamaSimpleHub Web UI
 * マルチエージェントチャットアプリケーション
 */

// ===========================
// グローバル変数
// ===========================

// API設定
const API_BASE_URL = 'http://localhost:8000/api/v1';
const API_TIMEOUT = 300000; // 300秒（5分）

// 会話履歴（final_answerのみを保持）
let messages = [];

// DOM要素
let chatContainer;
let chatForm;
let userInput;
let sendButton;
let resetButton;
let statusText;
let statusDot;
let charCount;

// ===========================
// 初期化
// ===========================

document.addEventListener('DOMContentLoaded', () => {
    // DOM要素の取得
    chatContainer = document.getElementById('chat-container');
    chatForm = document.getElementById('chat-form');
    userInput = document.getElementById('user-input');
    sendButton = document.getElementById('send-button');
    resetButton = document.getElementById('reset-button');
    statusText = document.getElementById('status-text');
    statusDot = document.querySelector('.status-dot');
    charCount = document.getElementById('char-count');

    // marked.jsの設定
    if (typeof marked !== 'undefined') {
        marked.setOptions({
            breaks: true,
            gfm: true,
            headerIds: false,
            mangle: false
        });
    }

    // イベントリスナーの設定
    chatForm.addEventListener('submit', handleSubmit);
    resetButton.addEventListener('click', handleReset);
    userInput.addEventListener('input', handleInput);

    // 初期状態の設定
    updateSendButtonState();
    
    // APIサーバーの接続チェック
    checkServerConnection();
});

// ===========================
// イベントハンドラー
// ===========================

/**
 * フォーム送信時の処理
 */
async function handleSubmit(event) {
    event.preventDefault();

    const userMessage = userInput.value.trim();
    if (!userMessage) return;

    // ユーザーメッセージを表示
    appendUserMessage(userMessage);

    // 入力フィールドをクリア
    userInput.value = '';
    updateCharCount();
    updateSendButtonState();

    // ローディング状態に設定
    setLoadingState(true);

    try {
        // APIリクエストを送信
        const response = await sendMessageToAPI(userMessage);

        // アシスタントの応答を表示
        appendAssistantMessage(response);

        // 会話履歴に最終回答を追加
        messages.push({
            role: 'assistant',
            content: response.final_answer
        });

    } catch (error) {
        console.error('API通信エラー:', error);
        appendErrorMessage(error.message);
    } finally {
        // ローディング状態を解除
        setLoadingState(false);
    }
}

/**
 * リセットボタンクリック時の処理
 */
function handleReset() {
    if (!confirm('会話履歴をすべてクリアしますか？')) {
        return;
    }

    // 会話履歴をクリア
    messages = [];

    // チャットコンテナをクリア
    chatContainer.innerHTML = `
        <div class="welcome-message">
            <h2>👋 ようこそ！</h2>
            <p>質問を入力してください。複数のAIエージェントが協力して回答します。</p>
        </div>
    `;

    // ステータスを更新
    updateStatus('準備完了', 'ready');
}

/**
 * 入力フィールド変更時の処理
 */
function handleInput() {
    updateCharCount();
    updateSendButtonState();
}

// ===========================
// API通信
// ===========================

/**
 * サーバー接続チェック
 */
async function checkServerConnection() {
    try {
        const response = await fetch(`${API_BASE_URL}/health`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        if (response.ok) {
            updateStatus('準備完了', 'ready');
        } else {
            updateStatus('サーバーエラー', 'error');
        }
    } catch (error) {
        updateStatus('サーバーに接続できません', 'error');
        console.error('接続チェックエラー:', error);
    }
}

/**
 * メッセージをAPIに送信
 */
async function sendMessageToAPI(userMessage) {
    // リクエストボディを構築
    const requestBody = messages.length === 0
        ? { prompt: userMessage }
        : { messages: [...messages, { role: 'user', content: userMessage }] };

    // タイムアウト処理付きのfetch
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), API_TIMEOUT);

    try {
        const response = await fetch(`${API_BASE_URL}/generate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody),
            signal: controller.signal
        });

        clearTimeout(timeoutId);

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(
                errorData.detail || 
                `サーバーエラー (${response.status})`
            );
        }

        const data = await response.json();
        
        // レスポンスの検証
        if (!data.final_answer) {
            throw new Error('サーバーから不正な応答を受信しました');
        }

        return data;

    } catch (error) {
        if (error.name === 'AbortError') {
            throw new Error('リクエストがタイムアウトしました（120秒）');
        }
        throw error;
    }
}

// ===========================
// UI更新
// ===========================

/**
 * ユーザーメッセージを追加
 */
function appendUserMessage(content) {
    // ウェルカムメッセージを削除
    const welcomeMessage = chatContainer.querySelector('.welcome-message');
    if (welcomeMessage) {
        welcomeMessage.remove();
    }

    // メッセージ要素を作成
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message user';

    messageDiv.innerHTML = `
        <div class="message-content">
            <div class="message-label">
                👤 あなた
            </div>
            <div class="message-text">${escapeHtml(content)}</div>
        </div>
    `;

    chatContainer.appendChild(messageDiv);
    scrollToBottom();

    // 会話履歴に追加
    messages.push({
        role: 'user',
        content: content
    });
}

/**
 * アシスタントメッセージを追加
 */
function appendAssistantMessage(response) {
    const { final_answer, review_comment, worker_responses, metadata } = response;

    // メッセージ要素を作成
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';

    // ワーカー回答リストのHTML生成
    const workerListHTML = worker_responses.map(worker => `
        <div class="worker-item">
            <div class="worker-header">
                <span class="worker-name">🤖 ${escapeHtml(worker.agent_name)}</span>
                <span class="worker-time">${worker.processing_time.toFixed(2)}秒</span>
            </div>
            <div class="worker-response ${worker.is_success ? '' : 'worker-error'}">
                ${worker.is_success ? renderMarkdown(worker.response) : escapeHtml(worker.response)}
            </div>
        </div>
    `).join('');

    messageDiv.innerHTML = `
        <div class="message-content">
            <div class="message-label">
                🤖 AI アシスタント
            </div>

            <!-- セクション1: ワーカーの回答（開閉式） -->
            <div class="response-section workers-section">
                <div class="section-header">
                    <h3 class="section-title">🧠 各ワーカーの回答</h3>
                    <button class="toggle-button" onclick="toggleWorkerList(this)">
                        ▶ 詳細を表示
                    </button>
                </div>
                <div class="worker-list">
                    ${workerListHTML}
                </div>
            </div>

            <!-- セクション2: レビューワーの評価（常時表示） -->
            <div class="response-section review-section">
                <div class="section-header">
                    <h3 class="section-title">🤖 レビューワーの評価</h3>
                </div>
                <div class="section-content">
                    <div class="review-text">${renderMarkdown(review_comment)}</div>
                </div>
            </div>

            <!-- セクション3: 最終回答（常時表示、強調） -->
            <div class="response-section final-section">
                <div class="section-header">
                    <h3 class="section-title">💡 最終回答</h3>
                </div>
                <div class="section-content">
                    <div class="final-answer">${renderMarkdown(final_answer)}</div>
                </div>
            </div>

            <!-- メタデータ -->
            <div class="metadata">
                <div class="metadata-item">
                    <span>⏱️ 処理時間: ${metadata.processing_time_seconds.toFixed(2)}秒</span>
                </div>
                <div class="metadata-item">
                    <span>✅ 成功: ${metadata.successful_workers}/${metadata.total_workers}</span>
                </div>
                ${metadata.failed_workers > 0 ? `
                    <div class="metadata-item">
                        <span>❌ 失敗: ${metadata.failed_workers}</span>
                    </div>
                ` : ''}
            </div>
        </div>
    `;

    chatContainer.appendChild(messageDiv);
    scrollToBottom();
}

/**
 * エラーメッセージを追加
 */
function appendErrorMessage(errorText) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.innerHTML = `
        <strong>⚠️ エラーが発生しました</strong>
        <div>${escapeHtml(errorText)}</div>
    `;

    chatContainer.appendChild(errorDiv);
    scrollToBottom();
}

/**
 * ワーカーリストの表示/非表示を切り替え
 */
function toggleWorkerList(button) {
    const workersSection = button.closest('.workers-section');
    const workerList = workersSection.querySelector('.worker-list');
    
    workerList.classList.toggle('visible');
    
    if (workerList.classList.contains('visible')) {
        button.textContent = '▼ 詳細を隠す';
    } else {
        button.textContent = '▶ 詳細を表示';
    }
}

/**
 * 最下部までスクロール
 */
function scrollToBottom() {
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

/**
 * ローディング状態の設定
 */
function setLoadingState(isLoading) {
    if (isLoading) {
        sendButton.disabled = true;
        sendButton.classList.add('loading');
        sendButton.querySelector('.button-text').textContent = '送信中...';
        sendButton.querySelector('.button-icon').textContent = '⏳';
        userInput.disabled = true;
        updateStatus('処理中...', 'loading');
    } else {
        sendButton.disabled = false;
        sendButton.classList.remove('loading');
        sendButton.querySelector('.button-text').textContent = '送信';
        sendButton.querySelector('.button-icon').textContent = '📤';
        userInput.disabled = false;
        updateStatus('準備完了', 'ready');
        updateSendButtonState();
    }
}

/**
 * ステータス表示の更新
 */
function updateStatus(text, state) {
    statusText.textContent = text;
    statusDot.className = 'status-dot';
    
    if (state === 'loading') {
        statusDot.classList.add('loading');
    } else if (state === 'error') {
        statusDot.classList.add('error');
    }
}

/**
 * 送信ボタンの状態を更新
 */
function updateSendButtonState() {
    const hasText = userInput.value.trim().length > 0;
    sendButton.disabled = !hasText || userInput.disabled;
}

/**
 * 文字数カウントの更新
 */
function updateCharCount() {
    const currentLength = userInput.value.length;
    charCount.textContent = `${currentLength} / 10000`;
    
    if (currentLength > 9000) {
        charCount.style.color = 'var(--error-color)';
    } else if (currentLength > 8000) {
        charCount.style.color = 'var(--warning-color)';
    } else {
        charCount.style.color = 'var(--text-muted)';
    }
}

// ===========================
// ユーティリティ関数
// ===========================

/**
 * Markdownをレンダリング（数式も処理）
 */
function renderMarkdown(text) {
    if (!text) return '';
    
    // marked.jsが利用可能な場合
    if (typeof marked !== 'undefined') {
        // Markdownをパース
        let html = marked.parse(text);
        
        // KaTeXが利用可能な場合、数式をレンダリング
        if (typeof katex !== 'undefined') {
            html = renderMath(html);
        }
        
        return html;
    }
    
    // フォールバック: エスケープのみ
    return escapeHtml(text);
}

/**
 * 数式をKaTeXでレンダリング
 */
function renderMath(html) {
    // ブロック数式: $$...$$
    html = html.replace(/\$\$([\s\S]+?)\$\$/g, (match, math) => {
        try {
            return katex.renderToString(math.trim(), {
                displayMode: true,
                throwOnError: false,
                output: 'html'
            });
        } catch (e) {
            console.error('KaTeX rendering error (display):', e);
            return match;
        }
    });
    
    // インライン数式: $...$（ただし$$を除外）
    html = html.replace(/(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)/g, (match, math) => {
        try {
            return katex.renderToString(math.trim(), {
                displayMode: false,
                throwOnError: false,
                output: 'html'
            });
        } catch (e) {
            console.error('KaTeX rendering error (inline):', e);
            return match;
        }
    });
    
    return html;
}

/**
 * HTMLエスケープ
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// グローバルスコープに公開（HTML内のonclick属性で使用）
window.toggleWorkerList = toggleWorkerList;
