# Script de batería de pruebas para deus-vault autodetección
# Ejecuta pruebas de lookup para varias plataformas y muestra los resultados
# Requiere: curl, backend corriendo en http://localhost:8000

# ── Películas ────────────────────────────────────────────────
NETFLIX_MOVIE_URL="https://www.netflix.com/watch/60000861?source=35"
# Disney+ detecta Mandalorian como serie (correcto), si se quiere pelicula usar otro
DISNEY_MOVIE_URL="https://www.disneyplus.com/movies/encanto/33q4DdMGHLts"
PRIME_MOVIE_URL="https://www.primevideo.com/-/es/detail/0LCOF5S7YR0UEA8EYW31TA7OF7/ref=atv_mv_hom_c_OB3e7ea8_brws_10_5?jic=8%7CEgR0dm9k"
MAX_MOVIE_URL="https://play.hbomax.com/feature/urn:hbo:feature:GXkRjxwMt3oNJjhsJATwo:type:feature"
STREMIO_MOVIE_URL="https://app.strem.io/shell-v4.4/#/detail/movie/tt0780504/tt0780504"

# ── Series ───────────────────────────────────────────────────
NETFLIX_SERIES_URL="https://www.netflix.com/title/80057281"
DISNEY_SERIES_URL="https://www.disneyplus.com/series/andor/3xsQKWG00GL5"
# Prime Video: usar ASIN directo (formato más fiable)
PRIME_SERIES_URL="https://www.primevideo.com/-/es/detail/0JL6LKQZSNFNK8ETYQNZUQ0P4D/ref=atv_br_def_r_br_c_unkc_1_10"
MAX_SERIES_URL="https://play.hbomax.com/page/urn:hbo:page:GVU2cggagzYNJjhsJATwo:type:series"
STREMIO_SERIES_URL="https://app.strem.io/shell-v4.4/#/detail/series/tt0944947/tt0944947"

# ── Libros ───────────────────────────────────────────────────
OPENLIBRARY_URL="https://openlibrary.org/works/OL45883W"
GOODREADS_URL="https://www.goodreads.com/book/show/5907.The_Hobbit"
GOOGLEBOOKS_URL="https://books.google.com/books?id=zyTCDAAAQBAJ"

# ── Manga ────────────────────────────────────────────────────
MANGA_GOODREADS_URL="https://www.goodreads.com/book/show/819028.Vagabond_Vol_1"
MANGA_OL_URL="https://openlibrary.org/works/OL16791578W"
MANGA_GOODREADS2_URL="https://www.goodreads.com/book/show/26970.Berserk_Vol_1"

# ── Otros ────────────────────────────────────────────────────
STEAM_URL="https://store.steampowered.com/app/620/Portal_2/"
SPOTIFY_URL="https://open.spotify.com/track/7ouMYWpwJ422jRcDASZB7P"

# Función para probar una URL
probar() {
  PLATAFORMA="$1"
  URL="$2"
  echo "\n==== $PLATAFORMA ===="
  ENCODED_URL=$(python3 -c "import urllib.parse; print(urllib.parse.quote('''$URL'''))")
  curl -s "http://127.0.0.1:8000/api/lookup/auto?url=$ENCODED_URL" | jq '{title,author,duration_minutes,episode_count,seasons,suggested_content_type,page_count,source_id}'
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
echo "  LIBROS"
echo "════════════════════════════════════════"
probar "OpenLibrary" "$OPENLIBRARY_URL"
probar "Goodreads" "$GOODREADS_URL"
probar "GoogleBooks" "$GOOGLEBOOKS_URL"

echo "\n════════════════════════════════════════"
echo "  MANGA"
echo "════════════════════════════════════════"
probar "Manga - Vagabond Vol.1 (Goodreads)" "$MANGA_GOODREADS_URL"
probar "Manga - Vagabond (OpenLibrary)" "$MANGA_OL_URL"
probar "Manga - Berserk Vol.1 (Goodreads)" "$MANGA_GOODREADS2_URL"

echo "\n════════════════════════════════════════"
echo "  OTROS"
echo "════════════════════════════════════════"
probar "Steam" "$STEAM_URL"
probar "Spotify" "$SPOTIFY_URL"
