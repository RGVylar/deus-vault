import { es, type Dict } from './es';
import { en } from './en';
import { pt } from './pt';

export type Locale = 'es' | 'en' | 'pt';
export type TKey = keyof typeof es;

const dicts: Record<Locale, Dict> = { es, en, pt };
const LS_KEY = 'deus_vault_lang';

export const i18n = $state({ locale: 'es' as Locale });

if (typeof localStorage !== 'undefined') {
	const stored = localStorage.getItem(LS_KEY);
	if (stored === 'es' || stored === 'en' || stored === 'pt') {
		i18n.locale = stored;
	} else {
		// Sin preferencia guardada: detectar por idioma del navegador/dispositivo.
		// No se persiste — solo una elección explícita en Ajustes escribe en localStorage.
		const nav = (navigator.language ?? 'es').slice(0, 2).toLowerCase();
		i18n.locale = nav === 'en' ? 'en' : nav === 'pt' ? 'pt' : 'es';
	}
	document.documentElement.lang = i18n.locale;
}

export function setLocale(l: Locale) {
	i18n.locale = l;
	try { localStorage.setItem(LS_KEY, l); } catch {}
	document.documentElement.lang = l;
}

export function t(key: TKey, params?: Record<string, string | number>): string {
	let s: string = dicts[i18n.locale][key] ?? es[key] ?? key;
	if (params) {
		for (const [k, v] of Object.entries(params)) s = s.replaceAll(`{${k}}`, String(v));
	}
	return s;
}

// Pluralización simple one/other — válida para es/en/pt.
export function tc(base: string, count: number, params?: Record<string, string | number>): string {
	return t(`${base}${count === 1 ? '_one' : '_other'}` as TKey, { count, ...params });
}

export function getLocaleTag(): string {
	return { es: 'es-ES', en: 'en-US', pt: 'pt-BR' }[i18n.locale];
}

export function fmtDate(d: Date, opts?: Intl.DateTimeFormatOptions): string {
	return d.toLocaleDateString(getLocaleTag(), opts);
}

export function fmtNumber(n: number, opts?: Intl.NumberFormatOptions): string {
	return n.toLocaleString(getLocaleTag(), opts);
}

export function fmtCurrency(n: number, currency = 'EUR', opts?: Intl.NumberFormatOptions): string {
	return n.toLocaleString(getLocaleTag(), { style: 'currency', currency, ...opts });
}
