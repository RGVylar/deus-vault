// ================================================================
// Deus Vault — Vault site content script
// Runs on vault.mugrelore.com — signals to the webapp that the
// extension is installed so it can hide the install banner.
// ================================================================

document.documentElement.setAttribute('data-dv-ext', '1');
