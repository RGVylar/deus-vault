# Script de batería de pruebas para deus-vault autodetección
# Ejecuta pruebas de lookup para varias plataformas y muestra los resultados
# Requiere: curl, backend corriendo en http://localhost:8000



# ── Películas ────────────────────────────────────────────────
NETFLIX_MOVIE_URL="https://www.netflix.com/watch/60000861?source=35"
DISNEY_MOVIE_URL="https://www.disneyplus.com/video/mandalorian"
PRIME_MOVIE_URL="https://www.primevideo.com/-/es/detail/0LCOF5S7YR0UEA8EYW31TA7OF7/ref=atv_mv_hom_c_OB3e7ea8_brws_10_5?jic=8%7CEgR0dm9k"
MAX_MOVIE_URL="https://www.max.com/es/es/movies/dune/0b70fd7d-b017-4bec-b2e0-7a1e7eabf9dc"
STREMIO_MOVIE_URL="https://app.strem.io/shell-v4.4/#/detail/movie/tt0780504/tt0780504"

# ── Series ───────────────────────────────────────────────────
NETFLIX_SERIES_URL="https://www.netflix.com/title/80057281"
DISNEY_SERIES_URL="https://www.disneyplus.com/series/andor/3xsQKWG00GL5"
PRIME_SERIES_URL="https://www.primevideo.com/detail/0JL6LKQZSNFNK8ETYQNZUQ0P4D/"
MAX_SERIES_URL="https://play.hbomax.com/page/urn:hbo:page:GVU2cggagzYNJjhsJATwo:type:series"
STREMIO_SERIES_URL="https://app.strem.io/shell-v4.4/#/detail/series/tt0944947/tt0944947"

# ── Otros ────────────────────────────────────────────────────
STEAM_URL="https://store.steampowered.com/app/620/Portal_2/"
SPOTIFY_URL="https://open.spotify.com/track/7ouMYWpwJ422jRcDASZB7P"
OPENLIBRARY_URL="https://openlibrary.org/works/OL45883W"
GOODREADS_URL="https://www.goodreads.com/book/show/5907.The_Hobbit"
GOOGLEBOOKS_URL="https://books.google.com/books?id=zyTCDAAAQBAJ"

# Función para probar una URL
probar() {
  PLATAFORMA="$1"
  URL="$2"
  echo "\n==== $PLATAFORMA ===="
  ENCODED_URL=$(python3 -c "import urllib.parse; print(urllib.parse.quote('''$URL'''))")
  curl -s "http://127.0.0.1:8000/api/lookup/auto?url=$ENCODED_URL" | jq
}

echo "════════════════════════════════════════"
echo "  PELÍCULAS"
echo "════════════════════════════════════════"
probar "Netflix (película)" "$NETFLIX_MOVIE_URL"
probar "Disney+ (película)" "$DISNEY_MOVIE_URL"
probar "Prime Video (película)" "$PRIME_MOVIE_URL"
probar "Max (película)" "$MAX_MOVIE_URL"
probar "Stremio (película)" "$STREMIO_MOVIE_URL"

echo "\n════════════════════════════════════════"
echo "  SERIES"
echo "════════════════════════════════════════"
probar "Netflix (serie)" "$NETFLIX_SERIES_URL"
probar "Disney+ (serie)" "$DISNEY_SERIES_URL"
probar "Prime Video (serie)" "$PRIME_SERIES_URL"
probar "Max (serie)" "$MAX_SERIES_URL"
probar "Stremio (serie)" "$STREMIO_SERIES_URL"

echo "\n════════════════════════════════════════"
echo "  OTROS"
echo "════════════════════════════════════════"
probar "Steam" "$STEAM_URL"
probar "Spotify" "$SPOTIFY_URL"
probar "OpenLibrary" "$OPENLIBRARY_URL"
probar "Goodreads" "$GOODREADS_URL"
probar "GoogleBooks" "$GOOGLEBOOKS_URL"
