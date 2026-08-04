/**
 * Secciones opcionales que el usuario puede desactivar desde Ajustes.
 *
 * No todo el mundo quiere usar la Bóveda de Deseos, por ejemplo — desactivarla
 * la quita de la navegación (sidebar + tab bar) sin borrar sus datos, así que
 * reactivarla más tarde la devuelve tal cual estaba.
 *
 * La configuración se guarda en localStorage, por lo que es independiente para
 * cada navegador y dispositivo.
 */

const LS_KEY = 'deus_vault_disabled_features';

export type OptionalFeature = 'wishlist';

function loadDisabled(): OptionalFeature[] {
	if (typeof localStorage === 'undefined') return [];
	try {
		const raw = localStorage.getItem(LS_KEY);
		const parsed = raw ? JSON.parse(raw) : [];
		return Array.isArray(parsed) ? parsed.filter((v) => typeof v === 'string') : [];
	} catch {
		return [];
	}
}

export const features = $state({
	disabled: loadDisabled(),
});

function persist() {
	try {
		localStorage.setItem(LS_KEY, JSON.stringify(features.disabled));
	} catch { /* modo privado del navegador: se pierde al cerrar, no es grave */ }
}

export function isFeatureEnabled(name: OptionalFeature): boolean {
	return !features.disabled.includes(name);
}

export function setFeatureEnabled(name: OptionalFeature, enabled: boolean) {
	const i = features.disabled.indexOf(name);
	if (enabled && i >= 0) features.disabled.splice(i, 1);
	else if (!enabled && i < 0) features.disabled.push(name);
	persist();
}
