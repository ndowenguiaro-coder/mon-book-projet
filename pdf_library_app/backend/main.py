import os
import shutil
import uuid
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

import models
import schemas
import auth
from database import engine, get_db

load_dotenv()  # charge backend/.env s'il existe (JWT_SECRET, etc.)

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="API Bibliothèque PDF & Audio",
    description="Gestion de la bibliothèque, des genres/catégories personnalisables et du streaming des PDF.",
    version="1.2.0",
)

# CORS utile seulement si le site est hébergé ailleurs que l'API (origine
# différente). Quand le site est servi par ce même serveur (voir le montage
# de web_app en bas du fichier), aucune requête cross-origin n'a lieu.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
PDF_DIR = os.path.join(UPLOAD_DIR, "pdfs")
COVER_DIR = os.path.join(UPLOAD_DIR, "covers")
WEB_APP_DIR = os.path.join(BASE_DIR, "..", "web_app")

os.makedirs(PDF_DIR, exist_ok=True)
os.makedirs(COVER_DIR, exist_ok=True)

app.mount("/static/covers", StaticFiles(directory=COVER_DIR), name="covers")


# ==========================================
# 0. AUTHENTIFICATION
# ==========================================

@app.post("/auth/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == user_in.email).first():
        raise HTTPException(status_code=400, detail="Un compte existe déjà avec cet email.")
    if len(user_in.password) < 8:
        raise HTTPException(status_code=400, detail="Le mot de passe doit contenir au moins 8 caractères.")

    new_user = models.User(
        email=user_in.email,
        hashed_password=auth.hash_password(user_in.password),
        display_name=user_in.display_name,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@app.post("/auth/login", response_model=schemas.Token)
def login(credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == credentials.email).first()
    if not user or not auth.verify_password(credentials.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect.")

    token = auth.create_access_token(data={"sub": str(user.id)})
    return schemas.Token(access_token=token)


@app.get("/auth/me", response_model=schemas.UserResponse)
def get_me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user


# ==========================================
# 1. GENRES & CATÉGORIES (entièrement personnalisables)
# ==========================================

@app.post("/genres/", response_model=schemas.GenreResponse, status_code=status.HTTP_201_CREATED)
def create_genre(
    genre: schemas.GenreCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if db.query(models.Genre).filter(models.Genre.name == genre.name).first():
        raise HTTPException(status_code=400, detail="Ce genre existe déjà.")
    new_genre = models.Genre(name=genre.name)
    db.add(new_genre)
    db.commit()
    db.refresh(new_genre)
    return new_genre


@app.get("/genres/", response_model=List[schemas.GenreResponse])
def get_genres(db: Session = Depends(get_db)):
    return db.query(models.Genre).all()


@app.delete("/genres/{genre_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_genre(
    genre_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    genre = db.query(models.Genre).filter(models.Genre.id == genre_id).first()
    if not genre:
        raise HTTPException(status_code=404, detail="Genre introuvable.")
    db.delete(genre)
    db.commit()


@app.post("/categories/", response_model=schemas.CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    category: schemas.CategoryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if db.query(models.Category).filter(models.Category.name == category.name).first():
        raise HTTPException(status_code=400, detail="Cette catégorie existe déjà.")
    new_cat = models.Category(name=category.name)
    db.add(new_cat)
    db.commit()
    db.refresh(new_cat)
    return new_cat


@app.get("/categories/", response_model=List[schemas.CategoryResponse])
def get_categories(db: Session = Depends(get_db)):
    return db.query(models.Category).all()


@app.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Catégorie introuvable.")
    db.delete(category)
    db.commit()


# ==========================================
# 2. LIVRES
# ==========================================

@app.post("/books/", response_model=schemas.BookResponse, status_code=status.HTTP_201_CREATED)
async def upload_book(
    title: str = Form(...),
    author: str = Form(...),
    description: Optional[str] = Form(None),
    genre_id: int = Form(...),
    category_id: int = Form(...),
    audio_url: Optional[str] = Form(None),
    pdf_file: UploadFile = File(...),
    cover_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Ajoute un livre avec son PDF et sa couverture (réservé aux utilisateurs connectés)."""
    if not pdf_file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Le fichier doit obligatoirement être un PDF.")

    if not db.query(models.Genre).filter(models.Genre.id == genre_id).first():
        raise HTTPException(status_code=404, detail="Genre introuvable.")
    if not db.query(models.Category).filter(models.Category.id == category_id).first():
        raise HTTPException(status_code=404, detail="Catégorie introuvable.")

    # Préfixe unique pour éviter qu'un nom de fichier identique n'écrase un
    # livre existant, et pour empêcher toute tentative de path traversal.
    safe_pdf_name = f"{uuid.uuid4().hex}_{os.path.basename(pdf_file.filename)}"
    pdf_path = os.path.join(PDF_DIR, safe_pdf_name)
    with open(pdf_path, "wb") as buffer:
        shutil.copyfileobj(pdf_file.file, buffer)

    cover_filename = None
    if cover_file:
        cover_filename = f"{uuid.uuid4().hex}_{os.path.basename(cover_file.filename)}"
        cover_path = os.path.join(COVER_DIR, cover_filename)
        with open(cover_path, "wb") as buffer:
            shutil.copyfileobj(cover_file.file, buffer)

    new_book = models.Book(
        title=title,
        author=author,
        description=description,
        genre_id=genre_id,
        category_id=category_id,
        pdf_filename=safe_pdf_name,
        cover_filename=cover_filename,
        audio_url=audio_url,
    )

    db.add(new_book)
    db.commit()
    db.refresh(new_book)
    return new_book


@app.get("/books/", response_model=List[schemas.BookResponse])
def get_books(
    genre_id: Optional[int] = None,
    category_id: Optional[int] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = None,  # "newest" | "popular"
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Liste des livres, filtrable par genre/catégorie/recherche.
    sort_by="newest" alimente la section "Nouveautés" de l'accueil,
    sort_by="popular" alimente "Les plus lus" (basé sur view_count)."""
    query = db.query(models.Book)

    if genre_id:
        query = query.filter(models.Book.genre_id == genre_id)
    if category_id:
        query = query.filter(models.Book.category_id == category_id)
    if search:
        like = f"%{search}%"
        query = query.filter(models.Book.title.ilike(like) | models.Book.author.ilike(like))

    if sort_by == "newest":
        query = query.order_by(models.Book.created_at.desc())
    elif sort_by == "popular":
        query = query.order_by(models.Book.view_count.desc())

    return query.offset(skip).limit(limit).all()


@app.get("/books/{book_id}", response_model=schemas.BookResponse)
def get_book_details(book_id: int, db: Session = Depends(get_db)):
    book = db.query(models.Book).filter(models.Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Livre non trouvé.")
    return book


@app.patch("/books/{book_id}/view", response_model=schemas.BookResponse)
def register_book_view(book_id: int, db: Session = Depends(get_db)):
    """Incrémente le compteur de lecture (appelé par l'app à l'ouverture d'un livre)."""
    book = db.query(models.Book).filter(models.Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Livre non trouvé.")
    book.view_count += 1
    db.commit()
    db.refresh(book)
    return book


@app.get("/books/{book_id}/download")
def download_pdf(book_id: int, db: Session = Depends(get_db)):
    """Téléchargement / streaming du PDF ; l'app peut le mettre en cache local."""
    book = db.query(models.Book).filter(models.Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Livre introuvable.")

    file_path = os.path.join(PDF_DIR, book.pdf_filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Le fichier PDF n'existe pas sur le serveur.")

    return FileResponse(path=file_path, filename=book.pdf_filename, media_type="application/pdf")


# ==========================================
# 3. FAVORIS (liés au compte utilisateur, protégés par JWT)
# ==========================================

@app.post("/favorites/", response_model=schemas.FavoriteResponse, status_code=status.HTTP_201_CREATED)
def add_favorite(
    book_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if not db.query(models.Book).filter(models.Book.id == book_id).first():
        raise HTTPException(status_code=404, detail="Livre introuvable.")
    existing = (
        db.query(models.Favorite)
        .filter(models.Favorite.book_id == book_id, models.Favorite.user_id == current_user.id)
        .first()
    )
    if existing:
        return existing
    fav = models.Favorite(book_id=book_id, user_id=current_user.id)
    db.add(fav)
    db.commit()
    db.refresh(fav)
    return fav


@app.delete("/favorites/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite(
    book_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    fav = (
        db.query(models.Favorite)
        .filter(models.Favorite.book_id == book_id, models.Favorite.user_id == current_user.id)
        .first()
    )
    if fav:
        db.delete(fav)
        db.commit()


@app.get("/favorites/", response_model=List[schemas.BookResponse])
def list_favorites(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    return (
        db.query(models.Book)
        .join(models.Favorite, models.Favorite.book_id == models.Book.id)
        .filter(models.Favorite.user_id == current_user.id)
        .all()
    )


# ==========================================
# 4. PROGRESSION DE LECTURE ("reprendre à la page exacte")
# ==========================================

@app.put("/books/{book_id}/progress", response_model=schemas.ReadingProgressResponse)
def update_reading_progress(
    book_id: int,
    payload: schemas.ReadingProgressUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if not db.query(models.Book).filter(models.Book.id == book_id).first():
        raise HTTPException(status_code=404, detail="Livre introuvable.")

    progress = (
        db.query(models.ReadingProgress)
        .filter(models.ReadingProgress.book_id == book_id, models.ReadingProgress.user_id == current_user.id)
        .first()
    )
    if progress:
        progress.current_page = payload.current_page
    else:
        progress = models.ReadingProgress(
            book_id=book_id, user_id=current_user.id, current_page=payload.current_page
        )
        db.add(progress)
    db.commit()
    db.refresh(progress)
    return progress


@app.get("/books/{book_id}/progress", response_model=Optional[schemas.ReadingProgressResponse])
def get_reading_progress(
    book_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    return (
        db.query(models.ReadingProgress)
        .filter(models.ReadingProgress.book_id == book_id, models.ReadingProgress.user_id == current_user.id)
        .first()
    )


# ==========================================
# 5. SITE WEB (servi par ce même serveur : un seul déploiement, une seule URL)
# ==========================================
# Monté en dernier pour ne jamais intercepter les routes API ci-dessus :
# FastAPI teste d'abord les routes déclarées, puis retombe sur ce montage
# pour tout ce qui reste (les fichiers du site).
if os.path.isdir(WEB_APP_DIR):
    app.mount("/", StaticFiles(directory=WEB_APP_DIR, html=True), name="web_app")
