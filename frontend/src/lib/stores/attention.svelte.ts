/**
 * Tiempo de atención — la señal de interés de la página de Azar.
 *
 * Mide cuánto tarda el usuario en volver a tirar después de que el rolodex
 * se para en un contenido. Si aguanta mirando la ficha, probablemente le
 * interesó; si tira otra vez a los dos segundos, probablemente no.
 *
 * OJO con el nombre: esto NO es "tiempo de visualización" (los minutos de
 * contenido consumido que viven en la BD y alimentan Rewind/Consumido). El
 * tiempo de atención es otra cosa: sólo mide la deliberación del usuario
 * delante de la tirada.
 *
 * Es información temporal y local:
 *  - vive únicamente en localStorage, nunca se manda al backend,
 *  - caduca sola (TTL de sesión) y está topada en número de items,
 *  - no es un historial: sirve para la sesión de azar que está ocurriendo.
 *
 * Se usa para dos cosas dentro de Azar:
 *  1. Enseñar al usuario qué le está enganchando más ahora mismo.
 *  2. Afinar la tirada: al elegir ganador entre los candidatos del mazo se
 *     pesa por afinidad con los rasgos (tipo, género, autor, época) que más
 *     atención se han llevado.
 */

import type { Content, ContentType } from '$lib/types';
import { releaseYear } from '$lib/utils';

const LS_KEY = 'deus_vault_attention';
const LS_TUNING = 'deus_vault_attention_tuning';

/** Un tramo más corto que esto es un descarte de reflejo, no atención. */
const MIN_SEGMENT_MS = 700;
/** Techo por tramo: una pestaña olvidada no puede valer una tarde entera. */
const MAX_SEGMENT_MS = 10 * 60 * 1000;
/** La señal es de la sesión de azar en curso: lo que no se toca caduca. */
const TTL_MS = 6 * 60 * 60 * 1000;
/** Tope de items recordados (los más viejos se van primero). */
const MAX_ENTRIES = 40;
/** A partir de aquí damos por hecho que el contenido enganchó. */
const INTEREST_MS = 20_000;
/** Por debajo de aquí fue un descarte rápido. */
const DISMISS_MS = 5_000;
/** Sin al menos esta variedad de items medidos, afinar sería adivinar. */
const MIN_ENTRIES_FOR_TUNING = 3;

export type TraitKind = 'type' | 'genre' | 'author' | 'decade';
export const TRAIT_KINDS: TraitKind[] = ['type', 'genre', 'author', 'decade'];

export interface AttentionEntry {
	id: number;
	title: string;
	type: ContentType;
	thumb: string | null;
	/** Rasgos codificados como `kind:value` — ver `traitsOf`. */
	traits: string[];
	/** Atención acumulada en ms (suma de todas las veces que ha salido). */
	ms: number;
	/** Veces que ha salido en el rolodex. */
	rolls: number;
	/** Abrió el contenido o el trailer desde la ficha. */
	launched: boolean;
	/** Lo marcó como consumido desde la ficha. */
	done: boolean;
	/** Última actualización, para el TTL. */
	at: number;
}

export type AttentionLevel = 'high' | 'mid' | 'low';

export interface TraitScore {
	kind: TraitKind;
	value: string;
	ms: number;
	items: number;
}

// ── Persistencia ──────────────────────────────────────────────────────────

function isEntry(v: unknown): v is AttentionEntry {
	if (!v || typeof v !== 'object') return false;
	const e = v as Record<string, unknown>;
	return typeof e.id === 'number' && typeof e.ms === 'number' &&
		typeof e.at === 'number' && Array.isArray(e.traits);
}

function load(): AttentionEntry[] {
	if (typeof localStorage === 'undefined') return [];
	try {
		const raw = localStorage.getItem(LS_KEY);
		const parsed = raw ? JSON.parse(raw) : [];
		if (!Array.isArray(parsed)) return [];
		const cutoff = Date.now() - TTL_MS;
		return parsed.filter(isEntry).filter((e) => e.at >= cutoff).slice(0, MAX_ENTRIES);
	} catch {
		return [];
	}
}

export const attention = $state({
	entries: load(),
	/** Afinado del azar activo por defecto; no hace nada hasta que hay señal. */
	tuning: typeof localStorage === 'undefined' || localStorage.getItem(LS_TUNING) !== '0',
});

function persist() {
	try {
		localStorage.setItem(LS_KEY, JSON.stringify(attention.entries));
		localStorage.setItem(LS_TUNING, attention.tuning ? '1' : '0');
	} catch { /* modo privado del navegador: se pierde al cerrar, no es grave */ }
}

export function setTuning(v: boolean) {
	attention.tuning = v;
	persist();
}

export function resetAttention() {
	attention.entries = [];
	openId = null;
	since = null;
	keepRunningHidden = false;
	try { localStorage.removeItem(LS_KEY); } catch { /* ver persist() */ }
}

// ── Rasgos ────────────────────────────────────────────────────────────────

/** La época sale del año de estreno, que hoy sólo se conoce en películas. */
function decadeOf(c: Content): string | null {
	const year = releaseYear(c);
	return year == null ? null : String(Math.floor(year / 10) * 10);
}

/** Rasgos por los que se puede parecer un contenido a otro, como `kind:value`. */
export function traitsOf(c: Content): string[] {
	const traits: string[] = [`type:${c.content_type}`];
	for (const g of (c.genres ?? '').split(',')) {
		const v = g.trim();
		if (v) traits.push(`genre:${v}`);
	}
	// `author` es el canal en YouTube, el autor en libros, el estudio en cine,
	// la cadena en series y el desarrollador en juegos: el "quién" del item.
	const author = (c.author ?? '').trim();
	if (author) traits.push(`author:${author}`);
	const decade = decadeOf(c);
	if (decade) traits.push(`decade:${decade}`);
	return traits;
}

export function splitTrait(trait: string): { kind: TraitKind; value: string } {
	const i = trait.indexOf(':');
	return { kind: trait.slice(0, i) as TraitKind, value: trait.slice(i + 1) };
}

// ── Cronómetro ────────────────────────────────────────────────────────────

let openId: number | null = null;
/** Momento en que empezó el tramo abierto; `null` = en pausa. */
let since: number | null = null;
/** Tras abrir el contenido fuera, esconder la pestaña no significa desatender. */
let keepRunningHidden = false;

function entryOf(id: number): AttentionEntry | undefined {
	return attention.entries.find((e) => e.id === id);
}

function flush() {
	if (openId == null || since == null) return;
	const delta = Date.now() - since;
	since = Date.now();
	if (delta < MIN_SEGMENT_MS) return;
	const entry = entryOf(openId);
	if (!entry) return;
	entry.ms += Math.min(delta, MAX_SEGMENT_MS);
	entry.at = Date.now();
	persist();
}

/** El rolodex se ha parado en `c`: empieza a contar su tiempo de atención. */
export function beginAttention(c: Content) {
	endAttention();
	let entry = entryOf(c.id);
	if (!entry) {
		entry = {
			id: c.id,
			title: c.title,
			type: c.content_type,
			thumb: c.thumbnail,
			traits: traitsOf(c),
			ms: 0,
			rolls: 0,
			launched: false,
			done: false,
			at: Date.now(),
		};
		attention.entries.unshift(entry);
		if (attention.entries.length > MAX_ENTRIES) attention.entries.length = MAX_ENTRIES;
	}
	entry.rolls += 1;
	entry.at = Date.now();
	openId = c.id;
	since = Date.now();
	keepRunningHidden = false;
	persist();
}

/** Cierra el tramo abierto — al volver a tirar, al salir de la página, etc. */
export function endAttention() {
	flush();
	openId = null;
	since = null;
	keepRunningHidden = false;
}

/** Se fue a ver el contenido (o el trailer): eso también es atención. */
export function markLaunched(id: number) {
	const entry = entryOf(id);
	if (!entry) return;
	entry.launched = true;
	entry.at = Date.now();
	if (openId === id) keepRunningHidden = true;
	persist();
}

/** Lo marcó como consumido: la señal de interés más fuerte que hay aquí. */
export function markDone(id: number) {
	const entry = entryOf(id);
	if (entry) {
		flush();
		entry.done = true;
		entry.at = Date.now();
	}
	endAttention();
	persist();
}

/**
 * Conecta el cronómetro al ciclo de vida de la pestaña y devuelve la limpieza
 * (pensado para `return` dentro del `onMount` de la página de Azar).
 *
 * Sin esto, dejar la pestaña abierta toda la noche contaría como atención.
 */
export function attachAttentionLifecycle(): () => void {
	if (typeof document === 'undefined') return () => {};
	const onVisibility = () => {
		if (document.visibilityState === 'hidden') {
			flush();
			if (!keepRunningHidden) since = null;
		} else if (openId != null && since == null) {
			since = Date.now();
		}
	};
	const onHide = () => endAttention();
	document.addEventListener('visibilitychange', onVisibility);
	window.addEventListener('pagehide', onHide);
	return () => {
		document.removeEventListener('visibilitychange', onVisibility);
		window.removeEventListener('pagehide', onHide);
		endAttention();
	};
}

// ── Lectura de la señal ───────────────────────────────────────────────────

/** Atención media por tirada: un item que sale tres veces no vale el triple. */
export function avgMs(e: AttentionEntry): number {
	return e.rolls > 0 ? e.ms / e.rolls : e.ms;
}

export function attentionLevel(e: AttentionEntry): AttentionLevel {
	if (e.done || e.launched || avgMs(e) >= INTEREST_MS) return 'high';
	if (avgMs(e) < DISMISS_MS) return 'low';
	return 'mid';
}

/** Items medidos, de más a menos atención. */
export function rankedItems(limit = 5): AttentionEntry[] {
	return attention.entries
		.filter((e) => e.ms >= MIN_SEGMENT_MS)
		.sort((a, b) => b.ms - a.ms)
		.slice(0, limit);
}

/** Cuánta atención se ha llevado cada rasgo, sumando todos los items. */
function traitTotals(): Map<string, TraitScore> {
	const totals = new Map<string, TraitScore>();
	for (const e of attention.entries) {
		if (e.ms <= 0) continue;
		for (const trait of e.traits) {
			const { kind, value } = splitTrait(trait);
			if (!TRAIT_KINDS.includes(kind)) continue;
			const acc = totals.get(trait) ?? { kind, value, ms: 0, items: 0 };
			acc.ms += e.ms;
			acc.items += 1;
			totals.set(trait, acc);
		}
	}
	return totals;
}

export function topTraits(kind: TraitKind, limit = 3): TraitScore[] {
	return [...traitTotals().values()]
		.filter((s) => s.kind === kind)
		.sort((a, b) => b.ms - a.ms)
		.slice(0, limit);
}

/** Hay bastante medido como para que afinar signifique algo. */
export function hasSignal(): boolean {
	return attention.entries.filter((e) => e.ms >= MIN_SEGMENT_MS).length >= MIN_ENTRIES_FOR_TUNING;
}

/** True cuando el afinado está encendido y además tiene datos con los que afinar. */
export function tuningActive(): boolean {
	return attention.tuning && hasSignal();
}

/**
 * Elige ganador entre los candidatos del mazo pesando por afinidad.
 *
 * Nadie queda fuera del sorteo: el favorito triplica sus opciones y un
 * descarte rápido las reduce, pero cualquiera puede salir — si no, Azar
 * dejaría de ser azar y se convertiría en una lista de recomendados.
 */
export function pickTuned(candidates: Content[]): Content {
	const fallback = candidates[candidates.length - 1];
	if (candidates.length < 2 || !tuningActive()) return fallback;

	const totals = traitTotals();
	const scores = candidates.map((c) =>
		traitsOf(c).reduce((sum, trait) => sum + (totals.get(trait)?.ms ?? 0), 0)
	);
	const max = Math.max(...scores);
	if (max <= 0) return fallback;

	const weights = candidates.map((c, i) => {
		let w = 1 + 2 * (scores[i] / max);
		const seen = entryOf(c.id);
		if (seen && seen.ms >= MIN_SEGMENT_MS && attentionLevel(seen) === 'low') w *= 0.4;
		return w;
	});
	const total = weights.reduce((a, b) => a + b, 0);
	let r = Math.random() * total;
	for (let i = 0; i < candidates.length; i++) {
		r -= weights[i];
		if (r <= 0) return candidates[i];
	}
	return fallback;
}

/** Géneros y tipos que más atención acumulan, para volcarlos en los filtros. */
export function suggestedFilters(): { genres: string[]; types: ContentType[] } {
	return {
		genres: topTraits('genre', 2).map((s) => s.value),
		types: topTraits('type', 1).map((s) => s.value as ContentType),
	};
}

/** Segundos por debajo del minuto, `2m 14s` por encima. */
export function formatAttention(ms: number): string {
	const total = Math.round(ms / 1000);
	if (total < 60) return `${total}s`;
	const m = Math.floor(total / 60);
	const s = total % 60;
	return s ? `${m}m ${s}s` : `${m}m`;
}
