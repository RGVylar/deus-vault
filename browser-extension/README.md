# Deus Vault Browser Extension

Extensión de Chrome/Firefox que rastrea automáticamente tu consumo de YouTube (y otros medios) en Deus Vault.

## Características

- **Auto-add**: tras 30 segundos de reproducción en YouTube, añade el vídeo a tu bóveda como pendiente
- **Auto-consume**: cuando el vídeo termina (>85% visto), te pregunta si marcarlo como visto
- **Pestaña en fondo**: funciona aunque YouTube esté minimizado — recibirás una notificación del sistema al terminar el vídeo
- **Pregunta al salir**: si abandonas un vídeo a medias (20–85%), te pregunta qué hacer
- **Popup universal**: click en el icono de la extensión para añadir o marcar cualquier contenido manualmente (YouTube, Netflix, Steam, Goodreads…)

## Instalación (Chrome / Edge)

1. Abre `chrome://extensions`
2. Activa **Modo desarrollador** (esquina superior derecha)
3. Haz clic en **Cargar sin empaquetar**
4. Selecciona la carpeta `browser-extension/`
5. La extensión aparecerá en la barra de herramientas

## Primera configuración

1. Haz clic en el icono **DV** de la barra de herramientas
2. Introduce tu email y contraseña de Deus Vault
3. La URL de la API se configura automáticamente (`https://vault.mugrelore.com/api`)
   - Si usas una instancia propia, despliega el campo "URL de la API" y cámbiala

## Uso

### En YouTube
- Abre cualquier vídeo — se añade solo tras 30 segundos
- El icono muestra el estado: `+` no en vault · `·` pendiente · `✓` visto
- Cuando el vídeo termina aparece un toast con las opciones

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
│   └── youtube.css       Estilos del toast
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
| Host: `youtube.com` | Inyectar el script de detección |
| Host: `vault.mugrelore.com` | Llamadas a la API |
