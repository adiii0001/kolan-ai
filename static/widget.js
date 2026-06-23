/* ============================================================
   KOLAN AI — CHAT WIDGET (adapted for backend POST /chat)
   Drop this in Shopify theme.liquid just before </body>.
   ============================================================ */

<!-- ============================================================
     PART 1: KOLAN PAGE CONTEXT (must be before widget)
     ============================================================ -->
<script>
(function() {
  'use strict';

  window.kolanContext = {
    pageType: "{{ request.page_type }}",
    pageTitle: document.title,
    url: window.location.href,
    timestamp: new Date().toISOString(),

    product: {% if product %}{
      id: {{ product.id }},
      title: {{ product.title | json }},
      handle: {{ product.handle | json }},
      type: {{ product.type | json }},
      vendor: {{ product.vendor | json }},
      price: {{ product.price | money_without_currency | json }},
      available: {{ product.available | json }},
      tags: {{ product.tags | json }},
      variants: [
        {% for variant in product.variants %}
        {
          id: {{ variant.id }},
          title: {{ variant.title | json }},
          price: {{ variant.price | money_without_currency | json }},
          available: {{ variant.available | json }},
          sku: {{ variant.sku | json }}
        }{% unless forloop.last %},{% endunless %}
        {% endfor %}
      ],
      description: {{ product.description | strip_html | truncate: 300 | json }}
    }{% else %}null{% endif %},

    collection: {% if collection %}{
      id: {{ collection.id }},
      title: {{ collection.title | json }},
      handle: {{ collection.handle | json }},
      productsCount: {{ collection.products_count }}
    }{% else %}null{% endif %},

    cart: {
      itemCount: {{ cart.item_count }},
      totalPrice: {{ cart.total_price | money_without_currency | json }},
      items: [
        {% for item in cart.items limit: 10 %}
        {
          title: {{ item.product.title | json }},
          handle: {{ item.product.handle | json }},
          variant: {{ item.variant.title | json }},
          quantity: {{ item.quantity }},
          price: {{ item.line_price | money_without_currency | json }},
          productType: {{ item.product.type | json }}
        }{% unless forloop.last %},{% endunless %}
        {% endfor %}
      ]
    },

    customer: {% if customer %}{
      firstName: {{ customer.first_name | json }},
      ordersCount: {{ customer.orders_count }}
    }{% else %}null{% endif %},

    announcementBanner: (function() {
      var banner = document.querySelector('.announcement-bar, [class*="banner"]');
      return banner ? banner.innerText.replace(/\n/g, ' ').trim() : "";
    })()
  };

  window.kolanQuickActions = (function() {
    var pageType = "{{ request.page_type }}";
    var actions = {
      'product': [
        { icon: '🐾', label: 'Safe for my pet?', message: 'Is this product safe for my pet?' },
        { icon: '📋', label: 'How to use?', message: 'How do I use this product?' },
        { icon: '📦', label: 'What is included?', message: 'What is included in this product?' },
        { icon: '💰', label: 'Any discounts?', message: 'Are there any discounts on this product?' }
      ],
      'collection': [
        { icon: '⭐', label: 'Best sellers', message: 'Show me the best sellers in this collection' },
        { icon: '🔄', label: 'Compare products', message: 'Help me compare products in this collection' },
        { icon: '🏷️', label: 'Best deal?', message: 'What is the best deal in this collection?' },
        { icon: '🆕', label: 'What is new?', message: 'What new products do you have?' }
      ],
      'cart': [
        { icon: '➕', label: 'Recommend add-on', message: 'Can you recommend an add-on for my cart items?' },
        { icon: '🏷️', label: 'Any discounts?', message: 'Are there any discounts I can apply?' },
        { icon: '🚚', label: 'Delivery time?', message: 'What is the delivery time for my order?' },
        { icon: '💰', label: 'Free shipping?', message: 'How much more do I need for free shipping?' }
      ],
      'index': [
        { icon: '🔥', label: 'Best Sellers', message: 'Show me best-selling products' },
        { icon: '🐶', label: 'For Dogs', message: 'What products do you have for dogs?' },
        { icon: '🐱', label: 'For Cats', message: 'What products do you have for cats?' },
        { icon: '🏷️', label: 'Current Offers', message: 'What offers and deals are available?' }
      ],
      'search': [
        { icon: '🔍', label: 'Help me find', message: 'Can you help me find what I am looking for?' },
        { icon: '⭐', label: 'Top rated', message: 'Show me your top rated products' },
        { icon: '💰', label: 'Budget picks', message: 'Show me affordable products under 500' }
      ]
    };
    var defaults = [
      { icon: '🛍️', label: 'Browse products', message: 'Show me your product catalog' },
      { icon: '🚚', label: 'Shipping info', message: 'What is your shipping policy?' },
      { icon: '🔄', label: 'Return policy', message: 'What is your return policy?' },
      { icon: '📞', label: 'Contact support', message: 'How can I contact customer support?' }
    ];
    return actions[pageType] || defaults;
  })();

  window.kolanGetSessionId = function() {
    var id = sessionStorage.getItem('kolan_chat_session');
    if (!id) {
      id = 'sess_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
      sessionStorage.setItem('kolan_chat_session', id);
    }
    return id;
  };

  document.addEventListener('cart:updated', function(e) {
    if (window.kolanContext && window.kolanContext.cart) {
      try {
        var c = (e.detail && e.detail.cart) ? e.detail.cart : null;
        if (c) {
          window.kolanContext.cart.itemCount = c.item_count || window.kolanContext.cart.itemCount;
          window.kolanContext.cart.totalPrice = c.total_price ? (c.total_price / 100) : window.kolanContext.cart.totalPrice;
        }
      } catch(err) {}
      document.dispatchEvent(new CustomEvent('kolan:context-updated', { detail: window.kolanContext }));
    }
  });

  document.dispatchEvent(new CustomEvent('kolan:context-updated', { detail: window.kolanContext }));
  console.log('[Kolan AI] Context loaded:', window.kolanContext.pageType);
})();
</script>

<!-- ============================================================
     PART 2: CHAT WIDGET HTML
     ============================================================ -->
<button id="chatToggle">
  <svg id="toggleIcon" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M12 2C6.48 2 2 5.58 2 10c0 2.52 1.56 4.76 4 6.22V22l4.2-2.52C10.78 19.82 11.38 19.84 12 19.84c5.52 0 10-3.58 10-7.84S17.52 2 12 2z"/>
    <circle cx="8" cy="10" r="1" fill="currentColor" stroke="none"/>
    <circle cx="12" cy="10" r="1" fill="currentColor" stroke="none"/>
    <circle cx="16" cy="10" r="1" fill="currentColor" stroke="none"/>
  </svg>
  Ask Kōlan
</button>

<div id="chatWidget">
  <div id="chatHeader">
    <div class="header-left">
      <div class="header-avatar" style="background: var(--kolan-green-muted); width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M12 2C6.5 2 2 6.5 2 12C2 15.3 3.6 18.2 6.1 20C6.1 14.5 10.5 10 16 10C16.8 10 17.6 10.1 18.3 10.3C19.4 8.7 20 6.7 20 4.5C18 4.5 14.5 5.5 12 2Z" fill="#2d6a4f"/>
          <path d="M17 14L17.8 16.2L20 17L17.8 17.8L17 20L16.2 17.8L14 17L16.2 16.2L17 14Z" fill="#ffd166"/>
          <path d="M9 7L9.4 8.1L10.5 8.5L9.4 8.9L9 10L8.6 8.9L7.5 8.5L8.6 8.1L9 7Z" fill="#ffd166"/>
        </svg>
      </div>
      <div class="header-text">
        <div class="header-title-row">
          <span class="header-title">Kōlan AI</span>
          <span class="header-status">
            <span class="status-dot"></span>
            Online
          </span>
        </div>
        <span class="header-subtitle">Eco-Friendly Shopping Assistant</span>
      </div>
    </div>
    <div class="header-actions">
      <button id="refreshChat" aria-label="Reset chat">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M1 4v6h6"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>
        </svg>
      </button>
      <button id="closeChat" aria-label="Close chat">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
    </div>
  </div>

  <div id="chatMessages"></div>

  <div id="chatInputArea">
    <div class="input-wrapper">
      <input type="text" id="aiQuestion" placeholder="Message Kōlan AI..." autocomplete="off" />
      <button id="sendBtn" aria-label="Send message">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <line x1="5" y1="12" x2="19" y2="12"/>
          <polyline points="12 5 19 12 12 19"/>
        </svg>
      </button>
    </div>
    <div class="powered-by">24x7 Shopping Assistance</div>
  </div>
</div>

<!-- ============================================================
     PART 3: STYLES
     ============================================================ -->
<style>
:root {
  --kolan-green-dark: #1b4332;
  --kolan-green: #2d6a4f;
  --kolan-green-mid: #40916c;
  --kolan-green-light: #52b788;
  --kolan-green-muted: #d8f3dc;
  --kolan-green-bg: #f0faf4;
  --surface-primary: #ffffff;
  --surface-secondary: #f8f9fa;
  --surface-tertiary: #f1f3f5;
  --text-primary: #1a1a2e;
  --text-secondary: #495057;
  --text-muted: #868e96;
  --border-light: #e9ecef;
  --border-medium: #dee2e6;
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.06);
  --shadow-md: 0 4px 16px rgba(0,0,0,0.08);
  --shadow-lg: 0 12px 40px rgba(0,0,0,0.12);
  --shadow-xl: 0 20px 60px rgba(0,0,0,0.15);
  --radius-sm: 10px;
  --radius-md: 16px;
  --radius-lg: 22px;
  --radius-full: 999px;
  --font: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

#chatToggle {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 99999;
  display: flex;
  align-items: center;
  gap: 10px;
  background: var(--kolan-green-dark);
  color: #fff;
  border: none;
  border-radius: var(--radius-full);
  padding: 14px 28px;
  cursor: pointer;
  font-family: var(--font);
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0.3px;
  box-shadow: var(--shadow-lg), 0 0 0 0 rgba(45,106,79,0.3);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  animation: togglePulse 3s ease-in-out infinite;
}
#chatToggle:hover {
  background: var(--kolan-green);
  box-shadow: var(--shadow-xl);
  transform: translateX(-50%) translateY(-2px);
  animation: none;
}
#chatToggle:active { transform: translateX(-50%) translateY(0); }
@keyframes togglePulse {
  0%, 100% { box-shadow: var(--shadow-lg), 0 0 0 0 rgba(45,106,79,0.3); }
  50% { box-shadow: var(--shadow-lg), 0 0 0 10px rgba(45,106,79,0); }
}
#toggleIcon { flex-shrink: 0; }

#chatWidget {
  position: fixed;
  bottom: 90px;
  left: 50%;
  transform: translateX(-50%) translateY(20px);
  width: 400px;
  max-width: calc(100vw - 32px);
  height: 620px;
  max-height: calc(100vh - 140px);
  background: var(--surface-primary);
  border-radius: var(--radius-lg);
  display: none;
  flex-direction: column;
  overflow: hidden;
  z-index: 99999;
  box-shadow: var(--shadow-xl);
  border: 1px solid var(--border-light);
  opacity: 0;
  transition: opacity 0.3s ease, transform 0.3s ease;
  font-family: var(--font);
}
#chatWidget.visible { opacity: 1; transform: translateX(-50%) translateY(0); }

#chatHeader {
  background: var(--surface-primary);
  padding: 16px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--border-light);
  min-height: 64px;
}
.header-left { display: flex; align-items: center; gap: 12px; }
.header-text { display: flex; flex-direction: column; gap: 1px; }
.header-title-row { display: flex; align-items: center; gap: 6px; }
.header-title { font-size: 14.5px; font-weight: 700; color: var(--text-primary); letter-spacing: -0.2px; line-height: 1.2; }
.header-subtitle { font-size: 11px; color: var(--text-muted); font-weight: 500; letter-spacing: 0.1px; }
.header-status {
  display: flex; align-items: center; gap: 4px; font-size: 10px;
  color: var(--kolan-green); font-weight: 600; background: var(--kolan-green-bg);
  padding: 1px 5px; border-radius: 4px; border: 1px solid var(--kolan-green-muted); line-height: 1.2;
}
.status-dot { width: 5px; height: 5px; border-radius: 50%; background: var(--kolan-green-light); animation: statusPulse 2s ease-in-out infinite; }
@keyframes statusPulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
.header-actions { display: flex; gap: 4px; align-items: center; }
.header-actions button {
  width: 34px; height: 34px; border: none; background: transparent; border-radius: 8px;
  cursor: pointer; display: flex; align-items: center; justify-content: center;
  color: var(--text-muted); transition: all 0.2s ease;
}
.header-actions button:hover { background: var(--surface-tertiary); color: var(--text-primary); }

#chatMessages {
  flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column;
  gap: 16px; background: var(--surface-secondary); scroll-behavior: smooth;
}
#chatMessages::-webkit-scrollbar { width: 5px; }
#chatMessages::-webkit-scrollbar-track { background: transparent; }
#chatMessages::-webkit-scrollbar-thumb { background: var(--border-medium); border-radius: 10px; }

.user-message {
  align-self: flex-end; max-width: 78%; background: var(--kolan-green-dark); color: #fff;
  padding: 12px 16px; border-radius: var(--radius-md) var(--radius-md) 6px var(--radius-md);
  font-size: 14px; line-height: 1.55; word-break: break-word; animation: msgSlideIn 0.3s ease;
}
.bot-message { align-self: flex-start; max-width: 88%; display: flex; gap: 10px; animation: msgSlideIn 0.3s ease; }
.message-avatar { width: 28px; height: 28px; min-width: 28px; border-radius: 8px; background: var(--kolan-green-muted); display: flex; align-items: center; justify-content: center; margin-top: 2px; }
.message-content { background: var(--surface-primary); border: 1px solid var(--border-light); padding: 14px 16px; border-radius: 6px var(--radius-md) var(--radius-md) var(--radius-md); font-size: 14px; line-height: 1.6; color: var(--text-primary); word-break: break-word; box-shadow: var(--shadow-sm); }
@keyframes msgSlideIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }

.welcome-message .message-content { display: flex; flex-direction: column; gap: 6px; }
.welcome-title { font-size: 16px; font-weight: 700; color: var(--text-primary); }
.welcome-sub { font-size: 14px; color: var(--text-secondary); margin-bottom: 4px; }

.thinking-indicator { display: flex; align-items: center; gap: 10px; padding: 0; }
.thinking-indicator .message-content { display: flex; align-items: center; gap: 10px; padding: 14px 18px; }
.thinking-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--kolan-green-mid); animation: thinkBlink 1.4s ease-in-out infinite; flex-shrink: 0; }
.thinking-text { color: var(--text-secondary); font-size: 13.5px; font-style: italic; }
@keyframes thinkBlink { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.25; transform: scale(0.85); } }

.typewriter-word { opacity: 0; animation: wordReveal 0.12s ease forwards; display: inline; }
@keyframes wordReveal { to { opacity: 1; } }

.suggestion-row { margin-top: 12px; display: flex; flex-wrap: wrap; gap: 8px; }
.suggestion-btn {
  background: var(--surface-tertiary); color: var(--text-primary); border: 1px solid var(--border-light);
  border-radius: var(--radius-full); padding: 8px 14px; cursor: pointer; font-size: 12.5px;
  font-weight: 500; font-family: var(--font); display: flex; align-items: center; gap: 5px;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}
.suggestion-btn:hover {
  background: var(--kolan-green-bg); border-color: var(--kolan-green-light);
  color: var(--kolan-green-dark); transform: translateY(-1.5px);
  box-shadow: 0 4px 12px rgba(82, 183, 136, 0.15);
}
.suggestion-icon { font-size: 13px; }

.product-card {
  display: flex; gap: 14px; align-items: flex-start; background: var(--surface-primary);
  border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: 14px;
  margin-top: 8px; box-shadow: var(--shadow-sm);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  animation: cardSlideUp 0.45s cubic-bezier(0.4, 0, 0.2, 1) forwards;
}
.product-card:hover { box-shadow: var(--shadow-md); transform: translateY(-2px); border-color: var(--border-medium); }
@keyframes cardSlideUp { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }
.product-image { width: 88px; height: 88px; object-fit: contain; background: var(--surface-secondary); border-radius: var(--radius-sm); border: 1px solid var(--border-light); flex-shrink: 0; }
.product-content { flex: 1; min-width: 0; }
.product-title { color: var(--kolan-green-dark); font-size: 13.5px; font-weight: 600; text-decoration: none; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; transition: color 0.2s ease; }
.product-title:hover { color: var(--kolan-green); text-decoration: underline; }
.product-price { color: var(--text-primary); margin-top: 4px; font-size: 15px; font-weight: 700; }
.cart-btn {
  width: 100%; margin-top: 10px; border: 1.5px solid var(--kolan-green);
  border-radius: var(--radius-full); padding: 10px; background: transparent; color: var(--kolan-green);
  font-family: var(--font); font-weight: 600; font-size: 12.5px; cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex; align-items: center; justify-content: center; gap: 6px;
}
.cart-btn:hover { background: var(--kolan-green); color: #fff; box-shadow: 0 4px 12px rgba(45, 106, 79, 0.2); }

#chatInputArea { padding: 12px 16px 14px; background: var(--surface-primary); border-top: 1px solid var(--border-light); }
.input-wrapper { display: flex; align-items: center; background: var(--surface-secondary); border: 1px solid var(--border-light); border-radius: var(--radius-full); padding: 4px 4px 4px 16px; transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1); }
.input-wrapper:focus-within { border-color: var(--kolan-green-light); background: var(--surface-primary); box-shadow: 0 0 0 3px rgba(82, 183, 136, 0.15), 0 4px 12px rgba(0,0,0,0.02); }
#aiQuestion { flex: 1; background: transparent; color: var(--text-primary); border: none; height: 38px; font-size: 14px; font-family: var(--font); }
#aiQuestion::placeholder { color: var(--text-muted); }
#aiQuestion:focus { outline: none; }
#sendBtn { width: 38px; height: 38px; flex-shrink: 0; border: none; border-radius: 50%; background: var(--kolan-green-dark); color: white; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1); }
#sendBtn:hover { background: var(--kolan-green); transform: scale(1.05) rotate(-5deg); box-shadow: 0 4px 10px rgba(45, 106, 79, 0.25); }
#sendBtn:active { transform: scale(0.95); }
.powered-by { text-align: center; font-size: 10.5px; color: var(--text-muted); margin-top: 8px; letter-spacing: 0.2px; }

@media (max-width: 480px) {
  #chatWidget { width: calc(100vw - 16px); height: calc(100vh - 120px); bottom: 80px; border-radius: var(--radius-md); }
  #chatToggle { padding: 12px 22px; font-size: 13px; }
}
</style>

<!-- ============================================================
     PART 4: JAVASCRIPT — ADAPTED FOR BACKEND POST /chat
     ============================================================ -->
<script>
const API_URL = "https://ai.kolan.co.in/chat";
const chatToggle = document.getElementById("chatToggle");
const chatWidget = document.getElementById("chatWidget");
const closeChat = document.getElementById("closeChat");
const refreshChat = document.getElementById("refreshChat");
const sendBtn = document.getElementById("sendBtn");

const BOT_AVATAR_SVG = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 2C6.5 2 2 6.5 2 12C2 15.3 3.6 18.2 6.1 20C6.1 14.5 10.5 10 16 10C16.8 10 17.6 10.1 18.3 10.3C19.4 8.7 20 6.7 20 4.5C18 4.5 14.5 5.5 12 2Z" fill="#2d6a4f"/><path d="M17 14L17.8 16.2L20 17L17.8 17.8L17 20L16.2 17.8L14 17L16.2 16.2L17 14Z" fill="#ffd166"/><path d="M9 7L9.4 8.1L10.5 8.5L9.4 8.9L9 10L8.6 8.9L7.5 8.5L8.6 8.1L9 7Z" fill="#ffd166"/></svg>';

function getWelcomeHTML() {
  var actions = window.kolanQuickActions || [
    { icon: '🔥', label: 'Best Sellers', message: 'Show me best-selling products' },
    { icon: '💰', label: 'Under ₹1000', message: 'Recommend products under 1000 rupees' },
    { icon: '🐾', label: 'Pet Wipes', message: 'Show some pet wipes' }
  ];
  var suggestionsHTML = actions.map(function(a) {
    return '<button class="suggestion-btn" onclick="setQuestion(\'' + a.message.replace(/'/g, "\\'") + '\')">' +
      '<span class="suggestion-icon">' + (a.icon || '💡') + '</span> ' + escapeHTML(a.label) + '</button>';
  }).join('\n');
  var ctx = window.kolanContext || {};
  var sub = 'How can I help you today?';
  if (ctx.pageType === 'product' && ctx.product) { sub = 'Ask me about <strong>' + escapeHTML(ctx.product.title) + '</strong>'; }
  else if (ctx.pageType === 'collection' && ctx.collection) { sub = 'Browsing <strong>' + escapeHTML(ctx.collection.title) + '</strong>?'; }
  else if (ctx.pageType === 'cart' && ctx.cart && ctx.cart.itemCount > 0) { sub = 'You have ' + ctx.cart.itemCount + ' items in cart.'; }
  else if (ctx.customer && ctx.customer.firstName) { sub = 'Hi ' + escapeHTML(ctx.customer.firstName) + '!'; }
  return '<div class="bot-message welcome-message"><div class="message-avatar">' + BOT_AVATAR_SVG + '</div><div class="message-content"><span class="welcome-title">Welcome to Kōlan AI</span><span class="welcome-sub">' + sub + '</span><div class="suggestion-row">' + suggestionsHTML + '</div></div></div>';
}

document.getElementById("chatMessages").innerHTML = getWelcomeHTML();

chatToggle.onclick = function() { chatWidget.style.display = "flex"; void chatWidget.offsetWidth; chatWidget.classList.add("visible"); };
closeChat.onclick = function() { chatWidget.classList.remove("visible"); setTimeout(function() { chatWidget.style.display = "none"; }, 300); };
refreshChat.onclick = function() { document.getElementById("aiQuestion").value = ''; document.getElementById("chatMessages").innerHTML = getWelcomeHTML(); };

function setQuestion(text) { document.getElementById("aiQuestion").value = text; askAI(); }
sendBtn.onclick = askAI;
document.getElementById("aiQuestion").addEventListener("keypress", function(e) { if (e.key === "Enter") askAI(); });

function typewriterReveal(container, htmlContent, callback) {
  container.innerHTML = '';
  var sequence = [];
  function traverse(n, p) {
    if (n.nodeType === Node.TEXT_NODE) { var t = n.nodeValue; var pts = t.split(/(\s+)/); pts.forEach(function(pt) { if (!pt) return; sequence.push({ type: /\s+/.test(pt) ? 'space' : 'word', value: pt, parent: p }); }); }
    else { var c = n.cloneNode(false); sequence.push({ type: 'element_open', element: c, parent: p }); for (var i = 0; i < n.childNodes.length; i++) { traverse(n.childNodes[i], c); } }
  }
  var d = document.createElement('div'); d.innerHTML = htmlContent;
  for (var j = 0; j < d.childNodes.length; j++) { traverse(d.childNodes[j], container); }
  if (sequence.length === 0) { if (callback) callback(); return; }
  var idx = 0, msgs = document.getElementById("chatMessages"), lst = 0;
  function next() {
    if (idx >= sequence.length) { if (msgs) msgs.scrollTo({ top: msgs.scrollHeight, behavior: 'smooth' }); if (callback) callback(); return; }
    var a = sequence[idx];
    if (a.type === 'element_open') { a.parent.appendChild(a.element); idx++; next(); }
    else if (a.type === 'space') { a.parent.appendChild(document.createTextNode(a.value)); idx++; next(); }
    else if (a.type === 'word') {
      var s = document.createElement('span'); s.className = 'typewriter-word'; s.style.opacity = '0'; s.style.transition = 'opacity 0.08s ease'; s.textContent = a.value; a.parent.appendChild(s);
      void s.offsetWidth; s.style.opacity = '1';
      if (msgs) { var r = msgs.getBoundingClientRect(), sr = s.getBoundingClientRect(), n = Date.now(); if (sr.bottom > r.bottom - 35 && n - lst > 200) { msgs.scrollTo({ top: msgs.scrollHeight, behavior: 'smooth' }); lst = n; } }
      idx++; setTimeout(next, 35 + Math.random() * 20);
    }
  }
  next();
}

function createThinkingIndicator() {
  var id = 'thinking-' + Date.now();
  return { id: id, html: '<div class="bot-message thinking-indicator" id="' + id + '"><div class="message-avatar">' + BOT_AVATAR_SVG + '</div><div class="message-content"><span class="thinking-dot"></span><span class="thinking-text">Thinking this through, just a moment...</span></div></div>' };
}

async function askAI() {
  var input = document.getElementById("aiQuestion"), question = input.value.trim();
  if (!question) return;
  var messages = document.getElementById("chatMessages");
  messages.innerHTML += '<div class="user-message">' + escapeHTML(question) + '</div>';
  var thinking = createThinkingIndicator();
  messages.innerHTML += thinking.html;
  messages.scrollTop = messages.scrollHeight;
  input.value = "";
  try {
    // Payload matches backend POST /chat: { message, session_id, context }
    var payload = {
      message: question,
      session_id: window.kolanGetSessionId ? window.kolanGetSessionId() : null,
      context: window.kolanContext || {}
    };
    var response = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    var data = await response.json();
    var el = document.getElementById(thinking.id); if (el) el.remove();
    var botMsg = document.createElement('div'); botMsg.className = 'bot-message';
    var contentId = 'answer-content-' + Date.now();
    botMsg.innerHTML = '<div class="message-avatar">' + BOT_AVATAR_SVG + '</div><div class="message-content" id="' + contentId + '"></div>';
    messages.appendChild(botMsg);
    var contentEl = document.getElementById(contentId);
    // Backend returns { answer, products } — products have { title, price, image_url, handle, available }
    typewriterReveal(contentEl, data.answer || data.text || "", function() {
      if (data.products && data.products.length) {
        data.products.forEach(function(product, idx) {
          setTimeout(function() {
            var card = document.createElement('div'); card.className = 'product-card';
            card.innerHTML = '<img class="product-image" src="' + (product.image_url || '') + '" alt="' + escapeHTML(product.title) + '" /><div class="product-content"><a class="product-title" href="/products/' + product.handle + '" target="_self">' + escapeHTML(product.title) + '</a><div class="product-price">₹' + (product.price || '') + '</div><a class="cart-btn" href="/products/' + product.handle + '" target="_self">View Product</a></div>';
            messages.appendChild(card);
            messages.scrollTo({ top: messages.scrollHeight, behavior: 'smooth' });
          }, idx * 120);
        });
      }
      var delay = (data.products && data.products.length) ? (data.products.length * 120 + 80) : 50;
      setTimeout(function() {
        var suggestionsToRender = (window.kolanQuickActions || []).slice(0, 3);
        if (suggestionsToRender.length > 0) {
          var html = '<div class="suggestion-row" style="padding: 0 0 0 38px;">';
          suggestionsToRender.forEach(function(item) {
            var label = item.label || item.message || item;
            var msg = item.message || item.label || item;
            var icon = item.icon || '💡';
            html += '<button class="suggestion-btn" onclick="setQuestion(\'' + msg.replace(/'/g, "\\'") + '\')"><span class="suggestion-icon">' + icon + '</span> ' + escapeHTML(label) + '</button>';
          });
          html += '</div>';
          var rowDiv = document.createElement('div'); rowDiv.innerHTML = html;
          messages.appendChild(rowDiv.firstElementChild);
          messages.scrollTo({ top: messages.scrollHeight, behavior: 'smooth' });
        }
      }, delay);
    });
  } catch (error) {
    console.error(error);
    var el2 = document.getElementById(thinking.id); if (el2) el2.remove();
    messages.innerHTML += '<div class="bot-message"><div class="message-avatar">' + BOT_AVATAR_SVG + '</div><div class="message-content">⚠️ Kōlan AI is temporarily unavailable. Please try again.</div></div>';
    messages.scrollTop = messages.scrollHeight;
  }
}

document.addEventListener('kolan:context-updated', function() {
  var msgs = document.getElementById('chatMessages');
  if (msgs && msgs.children.length === 1 && msgs.children[0].classList.contains('welcome-message')) {
    msgs.innerHTML = getWelcomeHTML();
  }
});

function escapeHTML(str) {
  var div = document.createElement('div');
  div.appendChild(document.createTextNode(str));
  return div.innerHTML;
}
</script>
