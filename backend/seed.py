import sys
sys.path.insert(0, ".")
from datetime import datetime, timezone
from app.database import SessionLocal
from app.models.content import Content

db = SessionLocal()

def dt(s):
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)

items = [
    # YouTube - Kurzgesagt (real-looking avatar via ui-avatars)
    dict(user_id=1, title="The Most Mindblowing Facts About the Universe", content_type="youtube", author="Kurzgesagt", duration_minutes=14, consumed=True, consumed_at=dt("2026-01-08T20:00:00"), channel_thumbnail="https://ui-avatars.com/api/?name=Kurzgesagt&size=88&background=f47521&color=fff&rounded=true&bold=true", source_id="yt_k1"),
    dict(user_id=1, title="Why You Are Probably Wrong About Everything", content_type="youtube", author="Kurzgesagt", duration_minutes=17, consumed=True, consumed_at=dt("2026-02-03T19:30:00"), channel_thumbnail="https://ui-avatars.com/api/?name=Kurzgesagt&size=88&background=f47521&color=fff&rounded=true&bold=true", source_id="yt_k2"),
    dict(user_id=1, title="The Science of Black Holes", content_type="youtube", author="Kurzgesagt", duration_minutes=19, consumed=True, consumed_at=dt("2026-03-05T21:00:00"), channel_thumbnail="https://ui-avatars.com/api/?name=Kurzgesagt&size=88&background=f47521&color=fff&rounded=true&bold=true", source_id="yt_k3"),
    dict(user_id=1, title="What Happens If We Terraform Mars?", content_type="youtube", author="Kurzgesagt", duration_minutes=16, consumed=True, consumed_at=dt("2026-04-12T20:00:00"), channel_thumbnail="https://ui-avatars.com/api/?name=Kurzgesagt&size=88&background=f47521&color=fff&rounded=true&bold=true", source_id="yt_k4"),
    # YouTube - Fireship
    dict(user_id=1, title="JavaScript is Actually Good Now", content_type="youtube", author="Fireship", duration_minutes=8, consumed=True, consumed_at=dt("2026-01-20T10:00:00"), channel_thumbnail="https://ui-avatars.com/api/?name=Fireship&size=88&background=1565c0&color=fff&rounded=true&bold=true", source_id="yt_f1"),
    dict(user_id=1, title="How Linux Changed the World", content_type="youtube", author="Fireship", duration_minutes=11, consumed=True, consumed_at=dt("2026-01-28T21:00:00"), channel_thumbnail="https://ui-avatars.com/api/?name=Fireship&size=88&background=1565c0&color=fff&rounded=true&bold=true", source_id="yt_f2"),
    dict(user_id=1, title="The Rust Programming Language in 100 Seconds", content_type="youtube", author="Fireship", duration_minutes=2, consumed=True, consumed_at=dt("2026-02-20T09:00:00"), channel_thumbnail="https://ui-avatars.com/api/?name=Fireship&size=88&background=1565c0&color=fff&rounded=true&bold=true", source_id="yt_f3"),
    dict(user_id=1, title="CSS Is Secretly Incredible", content_type="youtube", author="Fireship", duration_minutes=9, consumed=True, consumed_at=dt("2026-03-25T10:30:00"), channel_thumbnail="https://ui-avatars.com/api/?name=Fireship&size=88&background=1565c0&color=fff&rounded=true&bold=true", source_id="yt_f4"),
    dict(user_id=1, title="React is Dead, Long Live React", content_type="youtube", author="Fireship", duration_minutes=7, consumed=True, consumed_at=dt("2026-04-30T11:00:00"), channel_thumbnail="https://ui-avatars.com/api/?name=Fireship&size=88&background=1565c0&color=fff&rounded=true&bold=true", source_id="yt_f5"),
    # YouTube - MrBeast
    dict(user_id=1, title="I Spent 100 Days in the Ocean", content_type="youtube", author="MrBeast", duration_minutes=22, consumed=True, consumed_at=dt("2026-01-15T19:00:00"), channel_thumbnail="https://ui-avatars.com/api/?name=MrBeast&size=88&background=fdd835&color=111&rounded=true&bold=true", source_id="yt_m1"),
    dict(user_id=1, title="I Built a Theme Park in 30 Days", content_type="youtube", author="MrBeast", duration_minutes=25, consumed=True, consumed_at=dt("2026-02-14T18:00:00"), channel_thumbnail="https://ui-avatars.com/api/?name=MrBeast&size=88&background=fdd835&color=111&rounded=true&bold=true", source_id="yt_m2"),
    dict(user_id=1, title="Every Country In The World Tries My Cooking", content_type="youtube", author="MrBeast", duration_minutes=28, consumed=True, consumed_at=dt("2026-03-18T19:00:00"), channel_thumbnail="https://ui-avatars.com/api/?name=MrBeast&size=88&background=fdd835&color=111&rounded=true&bold=true", source_id="yt_m3"),
    # YouTube - Veritasium
    dict(user_id=1, title="The Biggest Unsolved Problem in Math", content_type="youtube", author="Veritasium", duration_minutes=31, consumed=True, consumed_at=dt("2026-02-28T20:00:00"), channel_thumbnail="https://ui-avatars.com/api/?name=Veritasium&size=88&background=e53935&color=fff&rounded=true&bold=true", source_id="yt_v1"),
    dict(user_id=1, title="Why Gravity Is Not A Force", content_type="youtube", author="Veritasium", duration_minutes=24, consumed=True, consumed_at=dt("2026-04-05T21:00:00"), channel_thumbnail="https://ui-avatars.com/api/?name=Veritasium&size=88&background=e53935&color=fff&rounded=true&bold=true", source_id="yt_v2"),
    # Movies - Netflix
    dict(user_id=1, title="Dune: Part Three", content_type="movie", author="Denis Villeneuve", duration_minutes=175, consumed=True, consumed_at=dt("2026-01-10T22:00:00"), collection="Netflix"),
    dict(user_id=1, title="The Irishman 2", content_type="movie", author="Martin Scorsese", duration_minutes=209, consumed=True, consumed_at=dt("2026-02-07T21:00:00"), collection="Netflix"),
    dict(user_id=1, title="Knives Out 3", content_type="movie", author="Rian Johnson", duration_minutes=130, consumed=True, consumed_at=dt("2026-03-20T20:30:00"), collection="Netflix"),
    # Movies - Prime Video
    dict(user_id=1, title="Blade Runner 2099", content_type="movie", author="Ridley Scott", duration_minutes=148, consumed=True, consumed_at=dt("2026-01-25T22:00:00"), collection="Prime Video"),
    # Movies - Filmin
    dict(user_id=1, title="El sol del futuro", content_type="movie", author="Nanni Moretti", duration_minutes=96, consumed=True, consumed_at=dt("2026-02-18T20:00:00"), collection="Filmin"),
    dict(user_id=1, title="Monster", content_type="movie", author="Hirokazu Koreeda", duration_minutes=126, consumed=True, consumed_at=dt("2026-04-01T21:00:00"), collection="Filmin"),
    # Movies - abandoned
    dict(user_id=1, title="Fast & Furious 47", content_type="movie", author="Justin Lin", duration_minutes=140, consumed=False, abandoned=True, abandoned_at=dt("2026-03-01T21:00:00"), collection="Netflix"),
    # Series - Netflix
    dict(user_id=1, title="Stranger Things 5", content_type="series", author="Duffer Brothers", duration_minutes=60, episode_count=9, seasons=1, consumed=True, consumed_at=dt("2026-01-20T22:00:00"), collection="Netflix"),
    dict(user_id=1, title="The Witcher: Blood Origin S2", content_type="series", author="Declan de Barra", duration_minutes=45, episode_count=6, seasons=1, consumed=True, consumed_at=dt("2026-03-10T22:00:00"), collection="Netflix"),
    # Series - HBO/Max
    dict(user_id=1, title="House of the Dragon S3", content_type="series", author="Ryan Condal", duration_minutes=65, episode_count=8, seasons=1, consumed=True, consumed_at=dt("2026-02-22T22:00:00"), collection="Max"),
    dict(user_id=1, title="The Last of Us S3", content_type="series", author="Craig Mazin", duration_minutes=55, episode_count=7, seasons=1, consumed=True, consumed_at=dt("2026-04-18T22:00:00"), collection="Max"),
    # Series - Disney+
    dict(user_id=1, title="Andor S2", content_type="series", author="Tony Gilroy", duration_minutes=45, episode_count=12, seasons=1, consumed=True, consumed_at=dt("2026-02-10T22:00:00"), collection="Disney+"),
    # Series - abandoned
    dict(user_id=1, title="The Crown S7", content_type="series", author="Peter Morgan", duration_minutes=50, episode_count=10, seasons=1, consumed=False, abandoned=True, abandoned_at=dt("2026-01-30T22:00:00"), collection="Netflix", progress=30),
    # Books
    dict(user_id=1, title="The Pragmatic Programmer", content_type="book", author="David Thomas", duration_minutes=840, page_count=352, words_per_page=300, consumed=True, consumed_at=dt("2026-01-30T18:00:00")),
    dict(user_id=1, title="Project Hail Mary", content_type="book", author="Andy Weir", duration_minutes=1080, page_count=476, words_per_page=300, consumed=True, consumed_at=dt("2026-02-25T18:00:00")),
    dict(user_id=1, title="Sapiens", content_type="book", author="Yuval Noah Harari", duration_minutes=1200, page_count=443, words_per_page=300, consumed=True, consumed_at=dt("2026-03-28T18:00:00")),
    dict(user_id=1, title="The Three-Body Problem", content_type="book", author="Liu Cixin", duration_minutes=960, page_count=400, words_per_page=300, consumed=True, consumed_at=dt("2026-04-22T18:00:00")),
    dict(user_id=1, title="Dune", content_type="book", author="Frank Herbert", duration_minutes=1440, page_count=688, words_per_page=300, consumed=False, abandoned=True, abandoned_at=dt("2026-03-15T18:00:00"), progress=45),
    # Games
    dict(user_id=1, title="Elden Ring: Shadow of the Erdtree", content_type="game", author="FromSoftware", duration_minutes=3600, consumed=True, consumed_at=dt("2026-01-28T00:00:00")),
    dict(user_id=1, title="Hollow Knight: Silksong", content_type="game", author="Team Cherry", duration_minutes=1800, consumed=True, consumed_at=dt("2026-03-08T00:00:00")),
    dict(user_id=1, title="Baldur's Gate 4", content_type="game", author="Larian Studios", duration_minutes=7200, consumed=False, abandoned=True, abandoned_at=dt("2026-04-10T00:00:00"), progress=25),
    # Music
    dict(user_id=1, title="Cowboy Carter (Deluxe)", content_type="music", author="Beyonce", duration_minutes=78, consumed=True, consumed_at=dt("2026-01-05T12:00:00")),
    dict(user_id=1, title="GNX", content_type="music", author="Kendrick Lamar", duration_minutes=42, consumed=True, consumed_at=dt("2026-02-10T12:00:00")),
    dict(user_id=1, title="The Tortured Poets Department", content_type="music", author="Taylor Swift", duration_minutes=65, consumed=True, consumed_at=dt("2026-03-14T12:00:00")),
    dict(user_id=1, title="Chromakopia", content_type="music", author="Tyler, the Creator", duration_minutes=57, consumed=True, consumed_at=dt("2026-04-20T12:00:00")),
]

# Clear previous data
db.query(Content).filter(Content.user_id == 1).delete()
db.commit()

for item in items:
    db.add(Content(**item))

db.commit()

total = db.query(Content).filter(Content.user_id == 1, Content.consumed == True).count()
abandoned = db.query(Content).filter(Content.user_id == 1, Content.abandoned == True).count()
print(f"Inserted {len(items)} items | consumed={total} | abandoned={abandoned}")
db.close()
