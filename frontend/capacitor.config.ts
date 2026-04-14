import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.deusvault.app',
  appName: 'Deus Vault',
  webDir: 'build',
  server: {
    androidScheme: 'https'
  }
};

export default config;
