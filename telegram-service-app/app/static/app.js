const tg = window.Telegram?.WebApp;

const state = {
  products: [],
  orders: [],
  discountPercent: 0,
  selectedProduct: null,
  activeCategory: "Все",
};

const productGrid = document.querySelector("#productGrid");
const categoryTabs = document.querySelector("#categoryTabs");
const checkoutTitle = document.querySelector("#checkoutTitle");
const selectedDescription = document.querySelector("#selectedDescription");
const selectedPrice = document.querySelector("#selectedPrice");
const selectedLeadTime = document.querySelector("#selectedLeadTime");
const comment = document.querySelector("#comment");
const counter = document.querySelector("#counter");
const submitOrder = document.querySelector("#submitOrder");
const formMessage = document.querySelector("#formMessage");
const userBadge = document.querySelector("#userBadge");
const ordersList = document.querySelector("#ordersList");
const refreshOrders = document.querySelector("#refreshOrders");

init();

async function init() {
  tg?.ready();
  tg?.expand();
  applyTelegramTheme();
  renderUser();

  comment.addEventListener("input", () => {
    counter.textContent = `${comment.value.length} / 2000`;
    updateSubmitState();
  });
  submitOrder.addEventListener("click", submitOrderForm);
  refreshOrders.addEventListener("click", loadMyOrders);

  await loadReferralStatus();
  await loadProducts();
  await loadMyOrders();
  if (tg?.initData) {
    window.setInterval(loadMyOrders, 20000);
  }
}

function applyTelegramTheme() {
  if (!tg?.themeParams) return;
  const root = document.documentElement;
  const theme = tg.themeParams;
  if (theme.bg_color) root.style.setProperty("--bg", theme.bg_color);
  if (theme.text_color) root.style.setProperty("--text", theme.text_color);
  if (theme.hint_color) root.style.setProperty("--muted", theme.hint_color);
  if (theme.button_color) root.style.setProperty("--accent", theme.button_color);
  if (theme.secondary_bg_color) root.style.setProperty("--surface-2", theme.secondary_bg_color);
}

function renderUser() {
  const user = tg?.initDataUnsafe?.user;
  if (!user) {
    userBadge.textContent = "Локальный тест";
    return;
  }
  userBadge.textContent = user.username ? `@${user.username}` : user.first_name;
}

async function loadProducts() {
  setMessage("Загружаем услуги...");
  try {
    const response = await fetch("/api/products");
    if (!response.ok) throw new Error("Не удалось загрузить услуги");
    const data = await response.json();
    state.products = data.products;
    state.selectedProduct = state.products[0] || null;
    renderCategories();
    renderProducts();
    renderSelectedProduct();
    setMessage("");
  } catch (error) {
    setMessage(error.message, "error");
  }
}

async function loadReferralStatus() {
  if (!tg?.initData) return;

  try {
    const response = await fetch("/api/referral/status", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ init_data: tg.initData }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Не удалось проверить скидку");
    state.discountPercent = data.discount_percent || 0;
  } catch (error) {
    state.discountPercent = 0;
  }
}

function renderCategories() {
  const categories = ["Все", ...new Set(state.products.map((product) => product.category))];
  categoryTabs.innerHTML = categories
    .map(
      (category) => `
        <button
          class="tab-button ${category === state.activeCategory ? "is-active" : ""}"
          type="button"
          data-category="${escapeAttribute(category)}"
        >
          ${escapeHtml(category)}
        </button>
      `,
    )
    .join("");

  categoryTabs.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeCategory = button.dataset.category;
      renderCategories();
      renderProducts();
    });
  });
}

function renderProducts() {
  const products = state.activeCategory === "Все"
    ? state.products
    : state.products.filter((product) => product.category === state.activeCategory);

  productGrid.innerHTML = products
    .map(
      (product) => `
        <article
          class="product-card ${state.selectedProduct?.id === product.id ? "is-selected" : ""}"
          data-product-id="${escapeAttribute(product.id)}"
          data-category="${escapeAttribute(product.category)}"
          tabindex="0"
        >
          <h3>${escapeHtml(product.title)}</h3>
          <p>${escapeHtml(product.description)}</p>
          <div class="product-meta">
            <span class="price-tag">${priceHtml(product.price_rub)}</span>
            <span class="time-tag">${escapeHtml(product.lead_time)}</span>
            <span class="category-tag">${escapeHtml(product.category)}</span>
          </div>
        </article>
      `,
    )
    .join("");

  productGrid.querySelectorAll(".product-card").forEach((card) => {
    const select = () => selectProduct(card.dataset.productId);
    card.addEventListener("click", select);
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        select();
      }
    });
  });
}

function selectProduct(productId) {
  state.selectedProduct = state.products.find((product) => product.id === productId);
  renderProducts();
  renderSelectedProduct();
  tg?.HapticFeedback?.selectionChanged();
}

function renderSelectedProduct() {
  const product = state.selectedProduct;
  if (!product) return;

  checkoutTitle.textContent = product.title;
  selectedDescription.textContent = product.description;
  selectedPrice.innerHTML = priceHtml(product.price_rub);
  selectedLeadTime.textContent = product.lead_time;
  updateSubmitState();
}

function updateSubmitState() {
  submitOrder.disabled = !state.selectedProduct || comment.value.trim().length < 5;
}

async function submitOrderForm() {
  if (!state.selectedProduct) return;
  submitOrder.disabled = true;
  setMessage("Отправляем заявку...");

  try {
    const response = await fetch("/api/orders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        product_id: state.selectedProduct.id,
        comment: comment.value.trim(),
        init_data: tg?.initData || "",
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Не удалось создать заявку");

    comment.value = "";
    counter.textContent = "0 / 2000";
    updateSubmitState();
    setMessage(`Заявка ${data.order.order_number} создана. Мы скоро свяжемся с вами.`, "success");
    await loadMyOrders();
    tg?.HapticFeedback?.notificationOccurred("success");
  } catch (error) {
    setMessage(error.message, "error");
    tg?.HapticFeedback?.notificationOccurred("error");
  } finally {
    updateSubmitState();
  }
}

async function loadMyOrders() {
  if (!tg?.initData) {
    renderOrdersMessage("Откройте каталог через Telegram, чтобы видеть свои заказы.");
    return;
  }

  refreshOrders.disabled = true;
  try {
    const response = await fetch("/api/orders/my", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ init_data: tg.initData }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Не удалось загрузить заказы");

    state.orders = data.orders;
    renderOrders();
  } catch (error) {
    renderOrdersMessage(error.message);
  } finally {
    refreshOrders.disabled = false;
  }
}

function renderOrders() {
  if (!state.orders.length) {
    renderOrdersMessage("Заказы появятся после оформления.");
    return;
  }

  ordersList.innerHTML = state.orders
    .map(
      (order) => `
        <article class="order-row">
          <div class="order-top">
            <div class="order-title">
              <span class="order-number">${escapeHtml(order.order_number)}</span>
              <span class="order-name">${escapeHtml(order.product_title)}</span>
            </div>
            <span class="order-status" data-status="${escapeAttribute(order.status)}">
              ${escapeHtml(order.status_label)}
            </span>
          </div>
          <div class="order-meta">
            <span>${orderPriceHtml(order)}</span>
            <span>${formatDate(order.created_at)}</span>
          </div>
          <p class="order-comment">${escapeHtml(trimComment(order.comment))}</p>
        </article>
      `,
    )
    .join("");
}

function renderOrdersMessage(text) {
  ordersList.innerHTML = `<p class="empty-orders">${escapeHtml(text)}</p>`;
}

function trimComment(value) {
  const text = String(value || "");
  return text.length > 120 ? `${text.slice(0, 120)}...` : text;
}

function setMessage(text, type = "") {
  formMessage.textContent = text;
  formMessage.className = `form-message ${type ? `is-${type}` : ""}`;
}

function formatRub(value) {
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "RUB",
    maximumFractionDigits: 0,
  }).format(value);
}

function priceHtml(price) {
  const discount = state.discountPercent || 0;
  if (!discount) return escapeHtml(formatRub(price));
  const finalPrice = Math.floor(price * (100 - discount) / 100);
  return `
    ${escapeHtml(formatRub(finalPrice))}
    <span class="old-price">${escapeHtml(formatRub(price))}</span>
    <span class="discount-note">-${discount}%</span>
  `;
}

function orderPriceHtml(order) {
  const discount = order.discount_percent || 0;
  const finalPrice = order.final_price_rub || order.price_rub;
  if (!discount) return escapeHtml(formatRub(finalPrice));
  return `
    ${escapeHtml(formatRub(finalPrice))}
    <span class="old-price">${escapeHtml(formatRub(order.original_price_rub || order.price_rub))}</span>
    <span class="discount-note">-${discount}%</span>
  `;
}

function formatDate(value) {
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttribute(value) {
  return escapeHtml(value).replaceAll("`", "&#096;");
}
