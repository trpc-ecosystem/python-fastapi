// FastAPI static-file example JavaScript
console.log('FastAPI 静态文件服务已加载');

// Show an alert
function showAlert() {
    const result = document.getElementById('result');
    const messages = [
        'Hello from FastAPI!',
        '静态文件服务正常工作！',
        'JavaScript 已成功加载！',
        'FastAPI 支持静态资源！',
        '这是一个动态消息！'
    ];
    
    const randomMessage = messages[Math.floor(Math.random() * messages.length)];
    result.innerHTML = `
        <div style="color: #27ae60; font-weight: bold;">
            ✅ ${randomMessage}
        </div>
        <div style="color: #666; font-size: 0.9em; margin-top: 5px;">
            时间: ${new Date().toLocaleString()}
        </div>
    `;
    
    // Play the fade-in animation
    result.style.animation = 'none';
    result.offsetHeight; // Force a reflow
    result.style.animation = 'fadeIn 0.5s ease-in-out';
}

// Initialize after the page loads
document.addEventListener('DOMContentLoaded', function() {
    console.log('页面加载完成');
    
    // Add hover effects
    const links = document.querySelectorAll('.links a');
    links.forEach(link => {
        link.addEventListener('mouseenter', function() {
            this.style.transform = 'translateX(5px) scale(1.05)';
        });
        
        link.addEventListener('mouseleave', function() {
            this.style.transform = 'translateX(0) scale(1)';
        });
    });
    
    // Add a keyboard shortcut
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && e.ctrlKey) {
            showAlert();
        }
    });
    
    // Show the shortcut hint
    setTimeout(() => {
        const result = document.getElementById('result');
        result.innerHTML = `
            <div style="color: #666; font-size: 0.9em;">
                💡 提示: 按 Ctrl+Enter 也可以触发按钮效果
            </div>
        `;
    }, 2000);
});

// Utility helpers
window.FastAPIUtils = {
    // Return the current time
    getCurrentTime: function() {
        return new Date().toLocaleString();
    },
    
    // Format a date
    formatDate: function(date) {
        return date.toLocaleDateString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    },
    
    // Show a notification
    showNotification: function(message, type = 'info') {
        const notification = document.createElement('div');
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 20px;
            background: ${type === 'success' ? '#27ae60' : type === 'error' ? '#e74c3c' : '#3498db'};
            color: white;
            border-radius: 5px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            z-index: 1000;
            animation: slideIn 0.3s ease-out;
        `;
        notification.textContent = message;
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease-in';
            setTimeout(() => {
                document.body.removeChild(notification);
            }, 300);
        }, 3000);
    }
};

// Inject CSS animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);
