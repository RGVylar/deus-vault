// ================================================================
// Deus Vault — Vault site content script
// Runs on vault.mugrelore.com — signals to the webapp that the
// extension is installed so it can hide the install banner.
// ================================================================

if (!window.__dvVaultInjected) {
  window.__dvVaultInjected = true;
  document.documentElement.setAttribute('data-dv-ext', '1');
}
