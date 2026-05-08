/** Shared store for global paste-to-add feature.
 *  Layout sets pendingUrl when a supported URL is pasted anywhere.
 *  The vault page watches it and opens the add modal.
 */
export const quickAdd = $state({ pendingUrl: '' });
