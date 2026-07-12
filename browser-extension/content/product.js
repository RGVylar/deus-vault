'use strict';

// ================================================================
// Deus Vault — Product page content script
// Extracts title, price and image from the live DOM.
// Runs on Amazon, Fnac, PCComponentes, MediaMarkt, El Corte Inglés,
// Zara, Apple, eBay and generic OG-tagged pages.
// ================================================================

function getStore() {
  const h = location.hostname.replace('www.', '');
  if (h.includes('amazon.'))        return 'amazon';
  if (h.includes('fnac.'))          return 'fnac';
  if (h.includes('pccomponentes.')) return 'pccomponentes';
  if (h.includes('mediamarkt.'))    return 'mediamarkt';
  if (h.includes('elcorteingles.')) return 'elcorteingles';
  if (h.includes('apple.'))         return 'apple';
  if (h.includes('ebay.'))          return 'ebay';
  if (h.includes('zalando.'))       return 'zalando';
  if (h.includes('zara.'))          return 'zara';
  return 'generic';
}

function parsePrice(raw) {
  if (!raw) return null;
  const cleaned = raw.replace(/[^\d.,]/g, '').trim();
  if (!cleaned) return null;
  if (cleaned.includes(',') && cleaned.includes('.')) {
    return parseFloat(
      cleaned.lastIndexOf(',') > cleaned.lastIndexOf('.')
        ? cleaned.replace(/\./g, '').replace(',', '.')
        : cleaned.replace(/,/g, '')
    );
  }
  if (cleaned.includes(',')) {
    const parts = cleaned.split(',');
    return parseFloat(parts[parts.length - 1].length <= 2
      ? cleaned.replace(',', '.')
      : cleaned.replace(/,/g, ''));
  }
  return parseFloat(cleaned);
}

function txt(sel) {
  const el = document.querySelector(sel);
  return el ? el.textContent.trim() : null;
}

function attr(sel, a) {
  const el = document.querySelector(sel);
  return el ? el.getAttribute(a) : null;
}

function extractAmazon() {
  const title = txt('#productTitle') || txt('#title');

  // Price: try rendered price first
  let priceRaw = null;
  const whole    = txt('.a-price-whole');
  const fraction = txt('.a-price-fraction');
  if (whole) {
    priceRaw = whole.replace(/[^\d]/g, '') + '.' + (fraction?.replace(/[^\d]/g, '') || '00');
  } else {
    priceRaw = txt('.a-offscreen') || txt('#priceblock_ourprice') || txt('#priceblock_dealprice');
  }

  const image = attr('#landingImage', 'src')
    || attr('#imgBlkFront', 'src')
    || attr('.a-dynamic-image', 'src');

  return { title, price: parsePrice(priceRaw), image };
}

function extractFnac() {
  return {
    title: txt('h1.f-productHeader-Title') || txt('h1'),
    price: parsePrice(txt('.f-priceBox-price') || txt('[class*="price"]')),
    image: attr('.productVisuals__main img', 'src') || attr('[class*="main"] img', 'src'),
  };
}

function extractPCComponentes() {
  return {
    title: txt('h1') || txt('[class*="product-title"]'),
    price: parsePrice(txt('[class*="price-final"]') || txt('[class*="buy-box__price"]') || txt('[class*="price"]')),
    image: attr('[class*="swiper-slide-active"] img', 'src') || attr('[class*="product"] img', 'src'),
  };
}

function extractMediaMarkt() {
  return {
    title: txt('[data-test="product-title"]') || txt('h1'),
    price: parsePrice(txt('[data-test="product-price"]') || txt('[class*="price"]')),
    image: attr('[data-test="product-image"] img', 'src') || attr('[class*="gallery"] img', 'src'),
  };
}

function extractElCorteIngles() {
  return {
    title: txt('h1[class*="product"]') || txt('h1'),
    price: parsePrice(txt('[class*="price__sale"]') || txt('[class*="price"]')),
    image: attr('[class*="gallery"] img', 'src') || attr('[class*="product"] img', 'src'),
  };
}

function extractApple() {
  return {
    title: txt('h1.hero-headline') || txt('[class*="typography-headline"]') || txt('h1'),
    price: parsePrice(txt('[class*="product-price"]') || txt('[data-analytics-price]') || txt('[class*="price"]')),
    image: attr('.product-hero img', 'src') || attr('[class*="hero"] img', 'src'),
  };
}

function extractEbay() {
  return {
    title: txt('#itemTitle') || txt('h1[class*="title"]') || txt('h1'),
    price: parsePrice(txt('#prcIsum') || txt('[itemprop="price"]') || txt('[class*="price"]')),
    image: attr('#icImg', 'src') || attr('[class*="img-gallery"] img', 'src'),
  };
}

function extractGeneric() {
  return {
    title: attr('meta[property="og:title"]', 'content') || txt('h1'),
    price: parsePrice(
      attr('meta[property="og:price:amount"]', 'content') ||
      attr('meta[property="product:price:amount"]', 'content') ||
      txt('[itemprop="price"]') ||
      txt('[class*="price"]')
    ),
    image: attr('meta[property="og:image"]', 'content') || attr('[class*="product"] img', 'src'),
  };
}

function extractProduct() {
  const store = getStore();
  let data;
  switch (store) {
    case 'amazon':        data = extractAmazon(); break;
    case 'fnac':          data = extractFnac(); break;
    case 'pccomponentes': data = extractPCComponentes(); break;
    case 'mediamarkt':    data = extractMediaMarkt(); break;
    case 'elcorteingles': data = extractElCorteIngles(); break;
    case 'apple':         data = extractApple(); break;
    case 'ebay':          data = extractEbay(); break;
    default:              data = extractGeneric(); break;
  }

  // Fallback: OG tags always win for image if store-specific selector failed
  if (!data.image) {
    data.image = attr('meta[property="og:image"]', 'content');
  }
  if (!data.title) {
    data.title = attr('meta[property="og:title"]', 'content') || document.title;
  }

  const storeName = location.hostname.replace('www.', '').split('.')[0];
  const storeLabel = storeName.charAt(0).toUpperCase() + storeName.slice(1);

  return {
    title:     data.title?.trim() || null,
    price:     isNaN(data.price) ? null : data.price,
    image_url: data.image || null,
    store:     storeLabel,
    url:       location.href,
  };
}

if (!window.__dvProductInjected) {
  window.__dvProductInjected = true;
  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg.type === 'GET_PRODUCT') {
      sendResponse(extractProduct());
    }
    return false;
  });
}
