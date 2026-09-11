import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
	// Con `--mode alt` se lee .env.alt (VITE_API_PROXY=http://127.0.0.1:8001) y
	// el frontend alternativo apunta al backend alternativo de .claude/launch.json.
	const env = loadEnv(mode, process.cwd(), '');
	return {
		plugins: [sveltekit()],
		server: {
			proxy: {
				'/api': env.VITE_API_PROXY || 'http://127.0.0.1:8000'
			}
		}
	};
});
