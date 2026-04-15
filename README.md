# Deus Vault

Bóveda de contenido por consumir antes de morir. Registra vídeos de YouTube, películas, libros y juegos, ve cuánto tiempo te queda por consumir, y deja que el azar decida cuando no sepas qué elegir.

## Stack

| Capa | Tecnología |
|------|-----------|
| Backend | FastAPI + SQLAlchemy + Alembic + PostgreSQL |
| Frontend | SvelteKit (adapter-static, PWA) |
| Mobile | SvelteKit + Capacitor |
| Auth | JWT + bcrypt |
| Deploy | Debian 12 LXC en Proxmox, systemd + Caddy + Cloudflare Tunnel |

## Funcionalidades

- **Contador total**: muestra la suma de duración de todo el contenido pendiente
- **Librería de contenido**: YouTube, películas, libros, juegos
- **Autodetección**: pega una URL de YouTube, Steam, Netflix, Prime Video, Max/HBO, Disney+ o Stremio y se rellena automáticamente
- **Enlaces directos**: abre en YouTube, Stremio, Steam o lanza el juego
- **Duración**: cada contenido muestra su tiempo estimado
- **Consumido**: marca como consumido y pasa a la colección de consumido
- **Balance**: ve el tiempo pendiente vs el tiempo ya consumido
- **Azar**: botón para elegir aleatoriamente qué consumir (filtrable por tipo)

## Desarrollo local

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
cp .env.example .env        # edita con tu PostgreSQL local
alembic upgrade head
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

El proxy de Vite redirige `/api` a `http://127.0.0.1:8000`.

## Deploy (Debian 12 LXC en Proxmox)

### Opción 1: Crear LXC desde cero (en host Proxmox)

```bash
# En el host Proxmox:
bash create-lxc.sh
# O con variables personalizadas:
CT_ID=210 CT_NAME=deusvault DOMAIN=vault.mugrelore.com bash create-lxc.sh
```

Variables disponibles:
- `CT_ID`: ID único del contenedor (default: 210)
- `CT_NAME`: nombre del hostname (default: deusvault)
- `CT_MEMORY`: RAM en MB (default: 2048)
- `CT_CORES`: CPUs (default: 2)
- `CT_DISK`: disco en GB (default: 20)
- `CT_STORAGE`: storage Proxmox (default: local-lvm)
- `DOMAIN`: dominio (default: vault.mugrelore.com)

### Opción 2: Instalar en LXC existente

```bash
# Dentro del LXC como root:
bash -c "$(curl -fsSL https://raw.githubusercontent.com/RGVylar/deus-vault/main/deploy/install.sh)"

# Para repos privados:
GITHUB_TOKEN=ghp_xxx bash -c "$(curl -fsSL ...)"
```

### Configurar Cloudflare Tunnel

Apunta tu Cloudflare Tunnel a `http://<CT_IP>:80` o `http://127.0.0.1:80` si estás en la misma red.

## Mobile (Capacitor)

```bash
cd frontend
npm run build
npx cap add android   # solo la primera vez
npx cap sync
npx cap open android
```

## Estructura

```
deus-vault/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI entry point
│   │   ├── config.py         # Settings (pydantic-settings)
│   │   ├── database.py       # SQLAlchemy engine + session
│   │   ├── security.py       # JWT + bcrypt
│   │   ├── deps.py           # get_current_user dependency
│   │   ├── models/
│   │   │   ├── user.py       # User model
│   │   │   └── content.py    # Content model (youtube/movie/book/game)
│   │   ├── schemas/
│   │   │   ├── auth.py       # Auth DTOs
│   │   │   └── content.py    # Content DTOs + VaultStats
│   │   └── routers/
│   │       ├── auth.py       # register / login / me
│   │       ├── contents.py   # CRUD + consume + random
│   │       └── lookup.py     # YouTube oEmbed + Steam API
│   ├── alembic/
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── lib/
│   │   │   ├── api.ts        # fetch wrapper + Capacitor detection
│   │   │   ├── types.ts      # TypeScript interfaces
│   │   │   ├── utils.ts      # formatDuration, buildConsumeUrl
│   │   │   └── stores/
│   │   │       └── auth.svelte.ts
│   │   └── routes/
│   │       ├── +page.svelte       # Bóveda principal
│   │       ├── consumed/          # Historial de consumido
│   │       ├── random/            # Selector aleatorio
│   │       ├── settings/          # Ajustes / logout
│   │       └── login/             # Login / registro
│   ├── capacitor.config.ts
│   └── package.json
└── deploy/
    ├── install.sh             # One-command installer
    ├── Caddyfile
    └── deus-vault-backend.service
```

## API Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/api/auth/register` | Crear cuenta |
| POST | `/api/auth/login` | Login → JWT |
| GET | `/api/auth/me` | Usuario actual |
| GET | `/api/contents` | Listar contenido (?consumed=&content_type=) |
| POST | `/api/contents` | Añadir contenido |
| PATCH | `/api/contents/:id` | Editar contenido |
| DELETE | `/api/contents/:id` | Eliminar contenido |
| POST | `/api/contents/:id/consume` | Marcar como consumido |
| POST | `/api/contents/:id/unconsume` | Devolver a pendiente |
| GET | `/api/contents/random` | Elegir al azar (?content_type=) |
| GET | `/api/contents/stats` | Estadísticas de la bóveda |
| GET | `/api/lookup/youtube?url=` | Auto-rellenar desde YouTube |
| GET | `/api/lookup/steam?url=` | Auto-rellenar desde Steam |
| GET | `/api/lookup/streaming?url=` | Auto-rellenar desde Netflix/Prime/Max/Disney/Stremio |
| GET | `/api/lookup/auto?url=` | Auto-detectar proveedor y auto-rellenar |

## Useful commands
```
pct exec 210 -- bash -lc '
cd /opt/deus-vault &&
sudo -u deusvault git pull &&
cd backend &&
sudo -u deusvault .venv/bin/pip install -e . &&
sudo -u deusvault .venv/bin/alembic upgrade head &&
cd ../frontend &&
sudo -u deusvault npm install --silent &&
sudo -u deusvault npm run build --silent &&
systemctl restart deus-vault-backend &&
systemctl reload caddy
'

pct exec 210 -- bash -c "cd /opt/deus-vault/backend && bash test_bateria_lookup.sh"
```