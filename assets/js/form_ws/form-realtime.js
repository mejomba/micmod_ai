// form-realtime.js - سینگلتون برای مدیریت چندین تب
class FormRealtimeManager {
    constructor() {
        this.connections = new Map(); // formId -> {ws, callbacks, reconnectAttempts}
        this.isSupported = 'WebSocket' in window;
        this.reconnectDelay = 1000;
        this.maxReconnectDelay = 30000;
    }

    connect(formId, onUpdate, onSync, onConflict) {
        if (this.connections.has(formId)) {
            const existing = this.connections.get(formId);
            existing.callbacks.push({ onUpdate, onSync, onConflict });
            return existing.ws;
        }

        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.host}/ws/form/${formId}/`;
        const ws = new WebSocket(wsUrl);

        let reconnectAttempts = 0;
        let currentDelay = this.reconnectDelay;

        ws.onopen = () => {
            console.log(`WebSocket connected for form ${formId}`);
            reconnectAttempts = 0;
            currentDelay = this.reconnectDelay;
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);

            switch(data.type) {
                case 'field_update':
                    // به‌روزرسانی فیلد خاص
                    this.connections.get(formId).callbacks.forEach(cb => {
                        if (cb.onUpdate) cb.onUpdate(data.field_name, data.value, data.user_id, data.timestamp);
                    });
                    break;

                case 'sync_state':
                    // همگام‌سازی کامل فرم
                    this.connections.get(formId).callbacks.forEach(cb => {
                        if (cb.onSync) cb.onSync(data.data, data.version);
                    });
                    break;

                case 'conflict':
                    // برطرف کردن تداخل
                    this.connections.get(formId).callbacks.forEach(cb => {
                        if (cb.onConflict) cb.onConflict(data.current_data);
                    });
                    break;

                case 'error':
                    console.error('WebSocket error:', data.message);
                    break;
            }
        };

        ws.onclose = () => {
            console.log(`WebSocket closed for form ${formId}, reconnecting...`);
            // تلاش مجدد با backoff
            setTimeout(() => {
                this.connect(formId, onUpdate, onSync, onConflict);
            }, currentDelay);

            currentDelay = Math.min(currentDelay * 2, this.maxReconnectDelay);
        };

        ws.onerror = (error) => {
            console.error(`WebSocket error for form ${formId}:`, error);
        };

        this.connections.set(formId, {
            ws,
            callbacks: [{ onUpdate, onSync, onConflict }],
            reconnectAttempts: 0
        });

        return ws;
    }

    updateField(formId, fieldName, value, currentVersion) {
        const conn = this.connections.get(formId);
        if (!conn || conn.ws.readyState !== WebSocket.OPEN) {
            console.warn(`Connection not ready for form ${formId}`);
            return false;
        }

        // Debounce برای جلوگیری از درخواست‌های پشت سر هم
        if (this.updateDebounce[`${formId}_${fieldName}`]) {
            clearTimeout(this.updateDebounce[`${formId}_${fieldName}`]);
        }

        this.updateDebounce[`${formId}_${fieldName}`] = setTimeout(() => {
            conn.ws.send(JSON.stringify({
                action: 'update_field',
                field_name: fieldName,
                value: value,
                client_version: currentVersion
            }));
        }, 100);

        return true;
    }

    disconnect(formId) {
        const conn = this.connections.get(formId);
        if (conn && conn.ws.readyState === WebSocket.OPEN) {
            conn.ws.close();
        }
        this.connections.delete(formId);
    }
}

// استفاده در هر فرم
const realtimeManager = new FormRealtimeManager();
let formVersion = 1;
let pendingUpdates = new Map();

// تابع کمکی برای ایجاد فرم واکنش‌گرا
function makeFormReactive(formElement, formId) {
    const fields = formElement.querySelectorAll('input, select, textarea');

    // نگاشت فیلدها با مقادیر جاری
    const fieldValues = new Map();

    // اتصال به WebSocket
    realtimeManager.connect(
        formId,
        // onUpdate: به‌روزرسانی فیلد از سرور
        (fieldName, value, userId, timestamp) => {
            const field = formElement.querySelector(`[name="${fieldName}"]`);
            if (field && field.value !== value) {
                // جلوگیری از حلقه بازخورد
                const oldValue = field.value;
                field.value = value;
                fieldValues.set(fieldName, value);

                // اعمال تغییرات در UI
                if (field.tagName === 'INPUT' && field.type === 'text') {
                    field.dispatchEvent(new Event('input', { bubbles: true }));
                }

                // نمایش نوتیفیکیشن کاربر تغییر
                showChangeNotification(field, userId, timestamp);
            }
        },
        // onSync: همگام‌سازی کامل
        (formData, version) => {
            formVersion = version;
            Object.entries(formData.data).forEach(([fieldName, value]) => {
                const field = formElement.querySelector(`[name="${fieldName}"]`);
                if (field && field.value !== value) {
                    field.value = value;
                    fieldValues.set(fieldName, value);
                }
            });
        },
        // onConflict: حل تداخل
        (currentData) => {
            if (confirm('داده‌های این فرم تغییر کرده است. آیا می‌خواهید صفحه را به‌روز کنید؟')) {
                location.reload();
            }
        }
    );

    // رویدادهای محلی
    fields.forEach(field => {
        let sendTimer;

        field.addEventListener('input', (e) => {
            const newValue = e.target.value;
            const fieldName = e.target.name;

            fieldValues.set(fieldName, newValue);

            // ارسال با تأخیر (debounce)
            if (sendTimer) clearTimeout(sendTimer);
            sendTimer = setTimeout(() => {
                realtimeManager.updateField(formId, fieldName, newValue, formVersion);
            }, 300);
        });

        // تغییر فوری برای چک‌باکس‌ها و رادیوها
        field.addEventListener('change', (e) => {
            if (field.type === 'checkbox' || field.type === 'radio') {
                realtimeManager.updateField(formId, field.name, field.value, formVersion);
            }
        });
    });

    // حفظ اتصال در بک‌گراند هنگام تغییر تب
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            // اولویت کمتر در تب‌های غیرفعال
            console.log('Tab inactive, keeping connection alive');
        } else {
            // درخواست همگام‌سازی مجدد هنگام فعال شدن تب
            realtimeManager.updateField(formId, '_sync', Date.now(), formVersion);
        }
    });
}

// نمایش نوتیفیکیشن تغییرات
function showChangeNotification(field, userId, timestamp) {
    const notification = document.createElement('div');
    notification.className = 'realtime-notification';
    notification.textContent = `User ${userId} changed this field ${new Date(timestamp).toLocaleTimeString()}`;
    notification.style.cssText = `
        position: absolute;
        background: #ff9800;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 12px;
        z-index: 1000;
        animation: fadeOut 2s forwards;
    `;

    const rect = field.getBoundingClientRect();
    notification.style.top = `${rect.top - 25}px`;
    notification.style.left = `${rect.left}px`;
    document.body.appendChild(notification);

    setTimeout(() => notification.remove(), 2000);
}

// محدود کردن تاریخچه تغییرات در حافظه
class FormStateHistory {
    constructor(maxSize = 50) {
        this.history = [];
        this.maxSize = maxSize;
    }

    push(state) {
        this.history.push(state);
        if (this.history.length > this.maxSize) {
            this.history.shift();
        }
    }

    getLastVersion() {
        return this.history[this.history.length - 1];
    }
}