# Script de batería de pruebas para deus-vault autodetección
# Ejecuta pruebas de lookup para varias plataformas y muestra los resultados
# Requiere: curl, backend corriendo en http://localhost:8000



# URLs de ejemplo para cada plataforma
NETFLIX_URL="https://www.netflix.com/watch/60000861?source=35"
DISNEY_URL="https://www.disneyplus.com/video/mandalorian"
PRIME_URL="https://www.primevideo.com/-/es/detail/0LCOF5S7YR0UEA8EYW31TA7OF7/ref=atv_mv_hom_c_OB3e7ea8_brws_10_5?jic=8%7CEgR0dm9k"
MAX_URL="https://play.hbomax.com/show/57660b16-a32a-476f-89da-3302ac379e91?utm_source=universal_search"
STREMIO_URL="https://app.strem.io/shell-v4.4/#/detail/movie/tt0780504/tt0780504"
STEAM_URL="https://store.steampowered.com/app/620/Portal_2/"
SPOTIFY_URL="https://open.spotify.com/track/7ouMYWpwJ422jRcDASZB7P"

# Función para probar una URL
probar() {
  PLATAFORMA="$1"
  URL="$2"
  echo "\n==== $PLATAFORMA ===="
  ENCODED_URL=$(python3 -c "import urllib.parse; print(urllib.parse.quote('''$URL'''))")
  curl -s "http://127.0.0.1:8000/api/lookup/auto?url=$ENCODED_URL" | jq
}

probar "Netflix" "$NETFLIX_URL"
probar "Disney+" "$DISNEY_URL"
probar "Prime Video" "$PRIME_URL"
probar "Max" "$MAX_URL"
probar "Stremio" "$STREMIO_URL"
probar "Steam" "$STEAM_URL"
probar "Spotify" "$SPOTIFY_URL"
