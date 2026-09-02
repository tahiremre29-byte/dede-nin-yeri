"use strict";

const state = {
  products: [],
  selectedProduct: null,
  currentDesign: null,
  currentInput: null,
};

const elements = {
  systemStatus: document.querySelector("#systemStatus"),
  wooferSelect: document.querySelector("#wooferSelect"),
  catalogMessage: document.querySelector("#catalogMessage"),
  designForm: document.querySelector("#designForm"),
  vehicleSelect: document.querySelector("#vehicleSelect"),
  purposeSelect: document.querySelector("#purposeSelect"),
  maxWidth: document.querySelector("#maxWidth"),
  maxHeight: document.querySelector("#maxHeight"),
  maxDepth: document.querySelector("#maxDepth"),
  calculateButton: document.querySelector("#calculateButton"),
  formError: document.querySelector("#formError"),
  resultCard: document.querySelector("#resultCard"),
  resultState: document.querySelector("#resultState"),
  emptyResult: document.querySelector("#emptyResult"),
  resultContent: document.querySelector("#resultContent"),
  resultBrand: document.querySelector("#resultBrand"),
  resultModel: document.querySelector("#resultModel"),
  netVolume: document.querySelector("#netVolume"),
  tuning: document.querySelector("#tuning"),
  portArea: document.querySelector("#portArea"),
  portLength: document.querySelector("#portLength"),
  dimensions: document.querySelector("#dimensions"),
  boxVisual: document.querySelector("#boxVisual"),
  fitResult: document.querySelector("#fitResult"),
  fitTitle: document.querySelector("#fitTitle"),
  fitText: document.querySelector("#fitText"),
  panelList: document.querySelector("#panelList"),
  reviewTitle: document.querySelector("#reviewTitle"),
  reviewText: document.querySelector("#reviewText"),
  feedbackStatus: document.querySelector("#feedbackStatus"),
  requestDialog: document.querySelector("#requestDialog"),
  productRequestForm: document.querySelector("#productRequestForm"),
  requestedProduct: document.querySelector("#requestedProduct"),
  requestStatus: document.querySelector("#requestStatus"),
  openRequest: document.querySelector("#openRequest"),
  closeRequest: document.querySelector("#closeRequest"),
  sendProductRequest: document.querySelector("#sendProductRequest"),
  openDetailedFeedback: document.querySelector("#openDetailedFeedback"),
  feedbackDialog: document.querySelector("#feedbackDialog"),
  detailedFeedbackForm: document.querySelector("#detailedFeedbackForm"),
  closeDetailedFeedback: document.querySelector("#closeDetailedFeedback"),
  detailedFeedback: document.querySelector("#detailedFeedback"),
  sendDetailedFeedback: document.querySelector("#sendDetailedFeedback"),
  detailedFeedbackStatus: document.querySelector("#detailedFeedbackStatus"),
};

const number = new Intl.NumberFormat("tr-TR", {
  maximumFractionDigits: 1,
  minimumFractionDigits: 0,
});

async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });

  let body = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }

  if (!response.ok) {
    throw new Error(readableError(body, response.status));
  }
  return body;
}

function readableError(body, status) {
  const detail = body?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail?.errors) && detail.errors.length) {
    return detail.errors.join(" ");
  }
  if (Array.isArray(detail) && detail.length) {
    return "Girilen bilgilerden biri uygun değil. Lütfen alanları kontrol et.";
  }
  if (status >= 500) return "Hesap servisi şu anda yanıt veremiyor. Lütfen tekrar dene.";
  return "İşlem tamamlanamadı. Bilgileri kontrol edip tekrar dene.";
}

function setConnection(kind, text) {
  elements.systemStatus.classList.remove("is-online", "is-offline");
  if (kind) elements.systemStatus.classList.add(`is-${kind}`);
  elements.systemStatus.lastElementChild.textContent = text;
}

function fillCatalog(payload) {
  state.products = Array.isArray(payload?.results) ? payload.results : [];
  elements.wooferSelect.replaceChildren();

  const prompt = document.createElement("option");
  prompt.value = "";
  prompt.textContent = state.products.length
    ? "Marka ve model seç"
    : "Beta ürün listesi hazırlanıyor";
  elements.wooferSelect.append(prompt);

  for (const product of state.products) {
    const option = document.createElement("option");
    option.value = String(product.model || "");
    option.textContent = [product.brand, product.model].filter(Boolean).join(" · ");
    elements.wooferSelect.append(option);
  }

  const hasProducts = state.products.length > 0;
  elements.wooferSelect.disabled = !hasProducts;
  elements.catalogMessage.hidden = false;
  elements.calculateButton.disabled = true;

  if (!payload?.configured) {
    elements.catalogMessage.querySelector("strong").textContent = "Onaylı ürün listesi henüz açılmadı.";
    elements.catalogMessage.querySelector("span").textContent = "Anlaşmalı ürünler doğrulandıkça burada görünecek.";
  } else if (hasProducts) {
    elements.catalogMessage.querySelector("strong").textContent = "Aradığın ürün listede yok mu?";
    elements.catalogMessage.querySelector("span").textContent = "Modeli bildir; doğrulama kuyruğuna ekleyelim.";
  } else {
    elements.catalogMessage.querySelector("strong").textContent = "Bu aramaya uygun ürün bulunamadı.";
    elements.catalogMessage.querySelector("span").textContent = "Modeli bildir; teknik verisini doğrulayalım.";
  }
}

async function initialize() {
  try {
    const [health, catalog] = await Promise.all([
      request("/health"),
      request("/api/public/products"),
    ]);
    if (health?.status !== "ok") throw new Error("Bağlantı kurulamadı.");
    setConnection("online", "DD1 hesap motoru hazır");
    fillCatalog(catalog);
  } catch (error) {
    setConnection("offline", "Hesap motoruna ulaşılamıyor");
    fillCatalog({ configured: false, results: [] });
    showFormError(error.message);
  }
}

function selectedProduct() {
  return state.products.find(
    (product) => String(product.model) === elements.wooferSelect.value,
  ) || null;
}

function showFormError(message) {
  elements.formError.textContent = message;
  elements.formError.hidden = false;
}

function clearFormError() {
  elements.formError.textContent = "";
  elements.formError.hidden = true;
}

function setCalculating(active) {
  elements.calculateButton.classList.toggle("is-loading", active);
  elements.calculateButton.disabled = active || !selectedProduct();
  elements.calculateButton.firstChild.textContent = active ? "Hesaplanıyor " : "Kabini hesapla ";
  elements.resultState.textContent = active ? "Fizik hesabı yapılıyor" : "Hesap bekleniyor";
  elements.resultState.classList.remove("is-ready");
}

function valueOrNull(input) {
  if (!input.value.trim()) return null;
  const parsed = Number(input.value);
  return Number.isFinite(parsed) ? parsed : null;
}

function requestPayload() {
  const payload = {
    woofer_model: state.selectedProduct.model,
    vehicle: elements.vehicleSelect.value,
    purpose: elements.purposeSelect.value,
  };
  const space = [
    valueOrNull(elements.maxWidth),
    valueOrNull(elements.maxHeight),
    valueOrNull(elements.maxDepth),
  ];
  if (space.every((value) => value !== null)) {
    payload.max_width_mm = space[0];
    payload.max_height_mm = space[1];
    payload.max_depth_mm = space[2];
  }
  return payload;
}

function metric(value, suffix) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? `${number.format(parsed)} ${suffix}` : "—";
}

function dimensionsOf(result) {
  const dimensions = result?.dimensions || {};
  return [Number(dimensions.w_mm), Number(dimensions.h_mm), Number(dimensions.d_mm)];
}

function renderBoxShape(dimensions) {
  const [width, height] = dimensions;
  if (!width || !height) return;
  const maxFace = 178;
  const ratio = Math.max(0.65, Math.min(1.65, width / height));
  const faceWidth = ratio >= 1 ? maxFace : maxFace * ratio;
  const faceHeight = ratio >= 1 ? maxFace / ratio : maxFace;
  elements.boxVisual.style.setProperty("--box-w", `${Math.round(faceWidth)}px`);
  elements.boxVisual.style.setProperty("--box-h", `${Math.round(faceHeight)}px`);
}

function renderFit(fitCheck) {
  elements.fitResult.classList.remove("is-fit", "is-no-fit");
  if (!fitCheck || fitCheck.status === "not_checked") {
    elements.fitTitle.textContent = "Alan ölçüsü eksik";
    elements.fitText.textContent = "Üç bagaj ölçüsünü de girersen ön sığma kontrolü yapılır.";
    return;
  }

  if (fitCheck.status === "fits") {
    elements.fitResult.classList.add("is-fit");
    elements.fitTitle.textContent = "Ön ölçü kontrolü olumlu";
    elements.fitText.textContent = "Kabin ölçüleri verilen alana bir yönde sığıyor. Bagaj ağzı araç üzerinde ayrıca ölçülmeli.";
  } else {
    elements.fitResult.classList.add("is-no-fit");
    elements.fitTitle.textContent = "Verilen alana sığmıyor";
    elements.fitText.textContent = "Bu taslak için daha geniş alan veya farklı bir ürün seçimi gerekiyor.";
  }
}

function renderPanelList(panels) {
  elements.panelList.replaceChildren();
  if (!Array.isArray(panels) || !panels.length) {
    const row = document.createElement("div");
    row.className = "panel-row";
    row.textContent = "Panel listesi bu taslakta oluşturulamadı.";
    elements.panelList.append(row);
    return;
  }

  for (const panel of panels) {
    const row = document.createElement("div");
    row.className = "panel-row";

    const name = document.createElement("strong");
    name.textContent = String(panel.ad || panel.name || "Panel");

    const size = document.createElement("span");
    const width = panel.en_mm ?? panel.width_mm ?? panel.w_mm ?? panel.w;
    const height = panel.boy_mm ?? panel.height_mm ?? panel.h_mm ?? panel.h;
    const count = panel.adet ?? panel.count ?? panel.qty ?? 1;
    size.textContent = `${metric(width, "mm")} × ${metric(height, "mm")} · ${count} adet`;

    row.append(name, size);
    elements.panelList.append(row);
  }
}

function renderResult(result) {
  state.currentDesign = result;
  elements.resultCard.classList.remove("is-empty");
  elements.emptyResult.hidden = true;
  elements.resultContent.hidden = false;
  elements.resultState.textContent = result.geometry_review_required
    ? "Akustik taslak hazır"
    : "Ön taslak hazır";
  elements.resultState.classList.add("is-ready");

  elements.resultBrand.textContent = state.selectedProduct.brand || "Doğrulanmış ürün";
  elements.resultModel.textContent = state.selectedProduct.model || "—";
  elements.netVolume.textContent = metric(result.net_volume_l, "L");
  elements.tuning.textContent = metric(result.tuning_hz, "Hz");
  elements.portArea.textContent = metric(result.port?.area_cm2, "cm²");
  elements.portLength.textContent = metric(result.port?.length_cm, "cm");

  const box = dimensionsOf(result);
  elements.dimensions.textContent = box.every(Number.isFinite)
    ? box.map((value) => number.format(value)).join(" × ") + " mm"
    : "—";

  renderBoxShape(box);
  renderFit(result.fit_check);
  renderPanelList(result.panel_list);
  if (result.geometry_review_required) {
    elements.reviewTitle.textContent = "Akustik hesap tamamlandı; geometri kontrolü gerekiyor.";
    elements.reviewText.textContent = "Bu panel ölçüleri kesim emri değildir. Port dönüşü, bagaj girişi ve fiziksel montaj DD Sound Garage tarafından doğrulanmalıdır.";
  } else {
    elements.reviewTitle.textContent = "Üretimden önce araç üzerinde son kontrol gerekir.";
    elements.reviewText.textContent = "Bagaj girişi, trimler ve fiziksel montaj alanı araç üzerinde doğrulanmalıdır.";
  }
  elements.feedbackStatus.textContent = "";
  document.querySelectorAll("[data-feedback]").forEach((button) => {
    button.disabled = false;
  });
}

elements.wooferSelect.addEventListener("change", () => {
  state.selectedProduct = selectedProduct();
  elements.calculateButton.disabled = !state.selectedProduct;
  clearFormError();
});

elements.designForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearFormError();
  state.selectedProduct = selectedProduct();
  if (!state.selectedProduct) {
    showFormError("Önce onaylı bir subwoofer modeli seç.");
    return;
  }

  const spaceValues = [elements.maxWidth, elements.maxHeight, elements.maxDepth]
    .map(valueOrNull);
  if (spaceValues.some((value) => value !== null) && spaceValues.some((value) => value === null)) {
    showFormError("Alan kontrolü için genişlik, yükseklik ve derinlik ölçülerinin üçünü de gir.");
    return;
  }

  state.currentInput = {
    vehicle: elements.vehicleSelect.value,
    purpose: elements.purposeSelect.value,
  };
  setCalculating(true);

  try {
    const result = await request("/api/public/design", {
      method: "POST",
      body: JSON.stringify(requestPayload()),
    });
    renderResult(result);
    elements.resultCard.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    showFormError(error.message);
    elements.resultState.textContent = "Hesap tamamlanamadı";
  } finally {
    setCalculating(false);
    if (state.currentDesign) {
      elements.resultState.textContent = state.currentDesign.geometry_review_required
        ? "Akustik taslak hazır"
        : "Ön taslak hazır";
      elements.resultState.classList.add("is-ready");
    }
  }
});

document.querySelectorAll("[data-feedback]").forEach((button) => {
  button.addEventListener("click", async () => {
    if (!state.currentDesign) return;
    elements.feedbackStatus.textContent = "Kaydediliyor…";
    try {
      await request("/api/public/feedback", {
        method: "POST",
        body: JSON.stringify({
          design_id: state.currentDesign.design_id,
          rating: Number(button.dataset.feedback),
          comment: button.dataset.comment,
          woofer_model: state.selectedProduct?.model || "",
          vehicle: state.currentInput?.vehicle || "",
          purpose: state.currentInput?.purpose || "",
        }),
      });
      elements.feedbackStatus.textContent = "Teşekkürler. Geri bildirimin geliştirme kaydına eklendi.";
      document.querySelectorAll("[data-feedback]").forEach((item) => {
        item.disabled = true;
      });
    } catch (error) {
      elements.feedbackStatus.textContent = error.message;
    }
  });
});

elements.openRequest.addEventListener("click", () => {
  elements.requestStatus.textContent = "";
  elements.requestDialog.showModal();
  elements.requestedProduct.focus();
});

elements.closeRequest.addEventListener("click", () => {
  elements.requestDialog.close();
});

elements.productRequestForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const product = elements.requestedProduct.value.trim();
  if (!product) return;

  elements.sendProductRequest.disabled = true;
  elements.requestStatus.textContent = "Gönderiliyor…";
  try {
    await request("/api/public/feedback", {
      method: "POST",
      body: JSON.stringify({
        design_id: "catalog_request",
        rating: 3,
        comment: `Ürün talebi: ${product}`,
        woofer_model: product,
      }),
    });
    elements.requestStatus.textContent = "Talep alındı. Teknik veri doğrulamasında değerlendireceğiz.";
    elements.requestedProduct.value = "";
    window.setTimeout(() => elements.requestDialog.close(), 1300);
  } catch (error) {
    elements.requestStatus.textContent = error.message;
  } finally {
    elements.sendProductRequest.disabled = false;
  }
});

elements.openDetailedFeedback.addEventListener("click", () => {
  if (!state.currentDesign) return;
  elements.detailedFeedbackStatus.textContent = "";
  elements.feedbackDialog.showModal();
  elements.detailedFeedback.focus();
});

elements.closeDetailedFeedback.addEventListener("click", () => {
  elements.feedbackDialog.close();
});

elements.detailedFeedbackForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const comment = elements.detailedFeedback.value.trim();
  if (!comment || !state.currentDesign) return;

  elements.sendDetailedFeedback.disabled = true;
  elements.detailedFeedbackStatus.textContent = "Kaydediliyor…";
  try {
    await request("/api/public/feedback", {
      method: "POST",
      body: JSON.stringify({
        design_id: state.currentDesign.design_id,
        rating: 3,
        comment,
        woofer_model: state.selectedProduct?.model || "",
        vehicle: state.currentInput?.vehicle || "",
        purpose: state.currentInput?.purpose || "",
      }),
    });
    elements.detailedFeedbackStatus.textContent = "Notun bu tasarımla birlikte geliştirme kaydına eklendi.";
    elements.detailedFeedback.value = "";
    window.setTimeout(() => elements.feedbackDialog.close(), 1400);
  } catch (error) {
    elements.detailedFeedbackStatus.textContent = error.message;
  } finally {
    elements.sendDetailedFeedback.disabled = false;
  }
});

initialize();
