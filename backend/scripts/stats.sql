-- deusstats
-- deus-vault · dashboard stats
-- Usage: psql $DATABASE_URL -f stats.sql
-- or:    pct exec <container> -- bash -c "psql \$DATABASE_URL -f /opt/deus-vault/backend/scripts/stats.sql"

\pset border 2
\pset linestyle unicode

-- ── 1. Resumen global ────────────────────────────────────────────────────────
\echo ''
\echo '══════════════════════ RESUMEN GLOBAL ══════════════════════'

SELECT
    (SELECT COUNT(*)             FROM users)                                        AS usuarios_total,
    (SELECT COUNT(*)             FROM users
        WHERE created_at >= NOW() - INTERVAL '7 days')                             AS nuevos_7d,
    (SELECT COUNT(*)             FROM users
        WHERE created_at >= NOW() - INTERVAL '30 days')                            AS nuevos_30d,
    (SELECT COUNT(*)             FROM contents)                                     AS items_total,
    (SELECT COUNT(*)             FROM contents WHERE consumed = true)               AS consumidos,
    (SELECT COUNT(*)             FROM contents WHERE abandoned = true)              AS abandonados,
    (SELECT COUNT(*)             FROM contents
        WHERE consumed = false AND abandoned = false)                               AS pendientes,
    (SELECT COUNT(*)             FROM contents
        WHERE progress IS NOT NULL
          AND consumed = false AND abandoned = false)                               AS en_progreso;

-- ── 2. Desglose por tipo de contenido ────────────────────────────────────────
\echo ''
\echo '══════════════════ DESGLOSE POR TIPO ════════════════════════'

SELECT
    content_type                                                        AS tipo,
    COUNT(*)                                                            AS total,
    COUNT(*) FILTER (WHERE consumed = true)                            AS consumidos,
    COUNT(*) FILTER (WHERE abandoned = true)                           AS abandonados,
    COUNT(*) FILTER (WHERE consumed = false AND abandoned = false)     AS pendientes,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE consumed = true)
        / NULLIF(COUNT(*), 0), 1
    )                                                                   AS pct_consumido,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE abandoned = true)
        / NULLIF(COUNT(*), 0), 1
    )                                                                   AS pct_abandono
FROM contents
GROUP BY content_type
ORDER BY total DESC;

-- ── 3. Top 10 usuarios más activos ───────────────────────────────────────────
\echo ''
\echo '══════════════════ TOP 10 USUARIOS MÁS ACTIVOS ══════════════'

SELECT
    u.id,
    u.name,
    u.email,
    COUNT(c.id)                                                         AS items_totales,
    COUNT(c.id) FILTER (WHERE c.consumed = true)                       AS consumidos,
    COUNT(c.id) FILTER (WHERE c.abandoned = true)                      AS abandonados,
    COUNT(c.id) FILTER (WHERE c.created_at >= NOW() - INTERVAL '7 days')  AS añadidos_7d,
    COUNT(c.id) FILTER (WHERE c.created_at >= NOW() - INTERVAL '30 days') AS añadidos_30d,
    MIN(c.created_at)::date                                             AS primer_item,
    MAX(c.created_at)::date                                             AS ultimo_item
FROM users u
JOIN contents c ON c.user_id = u.id
GROUP BY u.id, u.name, u.email
ORDER BY items_totales DESC
LIMIT 10;

-- ── 4. Tiempo estimado consumido por usuario (top 10) ────────────────────────
\echo ''
\echo '══════════════════ TOP 10 POR HORAS CONSUMIDAS ══════════════'
\echo '  (vídeo/juegos: duration_minutes · series: episodes×runtime · libros: páginas×wpm estimado)'

SELECT
    u.name,
    ROUND(SUM(
        CASE
            WHEN c.content_type = 'series'
                THEN COALESCE(c.episode_count, 1) * c.duration_minutes
            WHEN c.content_type = 'book'
                THEN COALESCE(c.page_count, 0) * COALESCE(c.words_per_page, 250) / 200  -- ~200 ppm
            ELSE c.duration_minutes
        END
    ) / 60.0, 1)                                                        AS horas_consumidas,
    COUNT(c.id)                                                         AS items_consumidos
FROM users u
JOIN contents c ON c.user_id = u.id
WHERE c.consumed = true
GROUP BY u.id, u.name
ORDER BY horas_consumidas DESC
LIMIT 10;

-- ── 5. Top 15 títulos más añadidos (entre distintos usuarios) ────────────────
\echo ''
\echo '══════════════════ TOP 15 TÍTULOS MÁS POPULARES ════════════'

SELECT
    title,
    content_type                                        AS tipo,
    COUNT(DISTINCT user_id)                             AS usuarios,
    COUNT(*)                                            AS veces_añadido,
    COUNT(*) FILTER (WHERE consumed = true)            AS veces_consumido,
    ROUND(AVG(rating)::numeric FILTER (WHERE rating IS NOT NULL), 2) AS rating_medio
FROM contents
GROUP BY title, content_type
HAVING COUNT(DISTINCT user_id) > 1
ORDER BY usuarios DESC, veces_añadido DESC
LIMIT 15;

-- ── 6. Tasa de abandono por tipo ─────────────────────────────────────────────
\echo ''
\echo '══════════════════ TASA DE ABANDONO POR TIPO ════════════════'

SELECT
    content_type                                        AS tipo,
    COUNT(*)                                            AS total,
    COUNT(*) FILTER (WHERE abandoned = true)           AS abandonados,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE abandoned = true)
        / NULLIF(COUNT(*), 0), 1
    )                                                   AS pct_abandono,
    ROUND(AVG(progress) FILTER (WHERE abandoned = true AND progress IS NOT NULL), 0) AS progreso_medio_al_abandonar
FROM contents
GROUP BY content_type
ORDER BY pct_abandono DESC;

-- ── 7. Colecciones más populares ─────────────────────────────────────────────
\echo ''
\echo '══════════════════ TOP 15 COLECCIONES ═══════════════════════'

SELECT
    collection,
    COUNT(DISTINCT user_id)                             AS usuarios,
    COUNT(*)                                            AS items,
    COUNT(*) FILTER (WHERE consumed = true)            AS consumidos,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE consumed = true)
        / NULLIF(COUNT(*), 0), 1
    )                                                   AS pct_consumido,
    array_agg(DISTINCT content_type::text)              AS tipos
FROM contents
WHERE collection IS NOT NULL
GROUP BY collection
ORDER BY items DESC
LIMIT 15;

-- ── 8. Actividad semanal (últimas 8 semanas) ─────────────────────────────────
\echo ''
\echo '══════════════════ ACTIVIDAD SEMANAL (8 semanas) ════════════'

SELECT
    DATE_TRUNC('week', created_at)::date                AS semana,
    COUNT(*)                                            AS items_añadidos,
    COUNT(*) FILTER (WHERE consumed = true
        AND consumed_at >= DATE_TRUNC('week', created_at)
        AND consumed_at <  DATE_TRUNC('week', created_at) + INTERVAL '7 days') AS consumidos_esa_semana,
    COUNT(DISTINCT user_id)                             AS usuarios_activos
FROM contents
WHERE created_at >= NOW() - INTERVAL '8 weeks'
GROUP BY DATE_TRUNC('week', created_at)::date
ORDER BY 1 DESC;

-- ── 9. Re-consumos (times_consumed > 1) ──────────────────────────────────────
\echo ''
\echo '══════════════════ TOP 10 RE-CONSUMOS ═══════════════════════'

SELECT
    u.name,
    c.title,
    c.content_type                                      AS tipo,
    c.times_consumed,
    ROUND(c.rating::numeric, 1)                         AS rating
FROM contents c
JOIN users u ON u.id = c.user_id
WHERE c.times_consumed > 1
ORDER BY c.times_consumed DESC
LIMIT 10;

-- ── 10. Géneros más populares ────────────────────────────────────────────────
\echo ''
\echo '══════════════════ TOP 20 GÉNEROS ═══════════════════════════'
\echo '  (extraídos del campo genres, separado por comas)'

SELECT
    TRIM(genre)                                         AS genero,
    COUNT(*)                                            AS apariciones,
    COUNT(DISTINCT user_id)                             AS usuarios,
    COUNT(*) FILTER (WHERE consumed = true)            AS consumidos,
    ROUND(AVG(rating)::numeric FILTER (WHERE rating IS NOT NULL), 2) AS rating_medio
FROM contents,
     UNNEST(STRING_TO_ARRAY(genres, ',')) AS genre
WHERE genres IS NOT NULL
GROUP BY TRIM(genre)
ORDER BY apariciones DESC
LIMIT 20;

-- ── 11. Ratings medios por tipo ───────────────────────────────────────────────
\echo ''
\echo '══════════════════ RATINGS POR TIPO ════════════════════════'

SELECT
    content_type                                        AS tipo,
    COUNT(*) FILTER (WHERE rating IS NOT NULL)         AS items_con_rating,
    ROUND(AVG(rating)::numeric FILTER (WHERE rating IS NOT NULL), 2) AS rating_medio,
    ROUND(MIN(rating)::numeric FILTER (WHERE rating IS NOT NULL), 2) AS rating_min,
    ROUND(MAX(rating)::numeric FILTER (WHERE rating IS NOT NULL), 2) AS rating_max
FROM contents
GROUP BY content_type
ORDER BY rating_medio DESC NULLS LAST;

\echo ''
\echo '═══════════════════════════════════════════════════════════════'
\echo 'Fin del informe.'
\echo ''
