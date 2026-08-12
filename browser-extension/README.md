# Deus Vault Browser Extension

Extensión de Chrome/Firefox que rastrea automáticamente tu consumo de YouTube (y otros medios) en Deus Vault.

## Características

- **Auto-add**: tras 30 segundos de reproducción en YouTube, añade el vídeo a tu bóveda como pendiente
- **Auto-consume**: cuando el vídeo termina (>85% visto), te pregunta si marcarlo como visto
- **Pestaña en fondo**: funciona aunque YouTube esté minimizado — recibirás una notificación del sistema al terminar el vídeo
- **Pregunta al salir**: si abandonas un vídeo a medias (20–85%), te pregunta qué hacer
- **Popup universal**: click en el icono de la extensión para añadir o marcar cualquier contenido manualmente (YouTube, Netflix, Steam, Goodreads…)
- **Bóveda de lo Perdido**: registra automáticamente el tiempo activo en contenido basura (YouTube Shorts, TikTok, Twitter/X, Instagram Reels) y lo muestra en la página `/wasted` de la app, comparado con el tiempo de contenido bueno consumido
- **Modo concentración**: temporizador que bloquea Shorts, TikTok, Twitter/X y Reels durante el tiempo que elijas. **No se puede cancelar** — no hay botón para pararlo

## Instalación (Chrome / Edge)

1. Abre `chrome://extensions`
2. Activa **Modo desarrollador** (esquina superior derecha)
3. Haz clic en **Cargar sin empaquetar**
4. Selecciona la carpeta `browser-extension/`
5. La extensión aparecerá en la barra de herramientas

## Primera configuración

1. Haz clic en el icono **DV** de la barra de herramientas
2. Introduce tu email y contraseña de Deus Vault
3. La URL de la API se configura automáticamente (`https://content.mugrelore.com/api`)

## Uso

### En YouTube
- Abre cualquier vídeo — se añade solo tras 30 segundos
- El icono muestra el estado: `+` no en vault · `·` pendiente · `✓` visto
- Cuando el vídeo termina aparece un toast con las opciones

### Modo concentración
- Haz clic en el icono **DV** → elige 25/50/90 minutos o escribe los que quieras (máx. 12h)
- Durante la sesión, cualquier visita a Shorts, TikTok, Twitter/X o Reels muestra una pantalla de bloqueo con la cuenta atrás, y pausa el vídeo que estuviera sonando
- El icono de la extensión muestra el tiempo restante
- Al terminar, el bloqueo se levanta solo y recibes una notificación

La sesión se guarda como un **timestamp de fin**, no como una cuenta atrás en memoria: sobrevive a cerrar la pestaña, cerrar Chrome, reiniciar el PC y a desactivar y reactivar la extensión. Empezar una sesión nueva mientras hay otra en marcha **suma** tiempo, nunca lo reduce.

Único hueco: si dejas la extensión desactivada en `chrome://extensions`, el bloqueo no se aplica (ninguna extensión puede impedirlo desde dentro) — pero pierdes también el tracker, y al reactivarla la sesión sigue corriendo si no ha vencido.

### En otras páginas (Netflix, Steam, Goodreads…)
- Haz clic en el icono **DV**
- La URL actual se pre-rellena en el campo de búsqueda
- Pulsa **Buscar** → el sistema detecta el tipo de contenido
- Usa los botones para añadir o marcar como visto

## Estructura de archivos

```
browser-extension/
├── manifest.json         MV3 manifest
├── service-worker.js     Lógica de API y notificaciones
├── content/
│   ├── youtube.js        Script inyectado en youtube.com
│   ├── youtube.css       Estilos del toast
│   ├── distraction.js    Tracker de tiempo perdido (Shorts, TikTok, X, Reels)
│   ├── focus.js          Bloqueo del modo concentración
│   └── focus.css         Estilos de la pantalla de bloqueo
├── popup/
│   ├── popup.html
│   ├── popup.js
│   └── popup.css
└── icons/
    ├── icon16.svg
    ├── icon48.svg
    └── icon128.svg
```

## Permisos requeridos

| Permiso | Motivo |
|---------|--------|
| `storage` | Guardar el token JWT y URL de la API |
| `notifications` | Notificaciones del sistema cuando el vídeo termina en segundo plano |
| `activeTab` | Leer la URL de la pestaña activa al abrir el popup |
| `tabs` | Enviar mensajes al content script de la pestaña activa |
| `alarms` | Terminar la sesión de concentración y refrescar la cuenta atrás del icono |
| Host: `youtube.com` | Inyectar el script de detección |
| Host: `tiktok.com`, `x.com`, `twitter.com`, `instagram.com` | Medir el tiempo perdido en contenido basura |
| Host: `content.mugrelore.com` | Llamadas a la API |
