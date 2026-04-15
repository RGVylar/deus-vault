# Script de batería de pruebas para deus-vault autodetección
# Ejecuta pruebas de lookup para varias plataformas y muestra los resultados
# Requiere: curl, backend corriendo en http://localhost:8000

# Ejemplos de títulos/URLs para cada plataforma
NETFLIX_TITLE="El Irlandés"
DISNEY_TITLE="The Mandalorian"
PRIME_TITLE="The Boys"
MAX_TITLE="Dune"
STREMIO_TITLE="Arcane"

# Puedes cambiar los títulos por URLs si tu endpoint los acepta

# Función para probar un título
probar() {
  PLATAFORMA="$1"
  TITULO="$2"
  echo "\n==== $PLATAFORMA ===="
  curl -s -X POST "http://localhost:8000/lookup" -H "Content-Type: application/json" -d "{\"title\": \"$TITULO\"}" | jq
}

probar "Netflix" "$NETFLIX_TITLE"
probar "Disney+" "$DISNEY_TITLE"
probar "Prime Video" "$PRIME_TITLE"
probar "Max" "$MAX_TITLE"
probar "Stremio" "$STREMIO_TITLE"
