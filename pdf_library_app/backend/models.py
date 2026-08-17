from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime, func
from sqlalchemy.orm import relationship
from database import Base


class Genre(Base):
    """Genre littéraire, entièrement personnalisable (CRUD via l'API)."""

    __tablename__ = "genres"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False, index=True)

    books = relationship("Book", back_populates="genre")


class Category(Base):
    """Catégorie personnalisée créée par l'utilisateur (ex: 'Roman noir',
    'Jeunesse'). À NE PAS confondre avec les sections dynamiques de
    l'accueil ('Nouveautés', 'Les plus lus'), qui sont calculées via un tri
    sur created_at / view_count, ni avec 'Téléchargés' / 'Favoris', qui sont
    des états propres à chaque appareil et gérés côté app Flutter."""

    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False, index=True)

    books = relationship("Book", back_populates="category")


class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(150), nullable=False, index=True)
    author = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    pdf_filename = Column(String(255), nullable=False)
    cover_filename = Column(String(255), nullable=True)
    audio_url = Column(String(255), nullable=True)  # audio pré-enregistré optionnel

    view_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    genre_id = Column(Integer, ForeignKey("genres.id"))
    category_id = Column(Integer, ForeignKey("categories.id"))

    genre = relationship("Genre", back_populates="books")
    category = relationship("Category", back_populates="books")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    display_name = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    favorites = relationship("Favorite", back_populates="user", cascade="all, delete-orphan")
    reading_progress = relationship("ReadingProgress", back_populates="user", cascade="all, delete-orphan")


class Favorite(Base):
    """Livre marqué favori par un utilisateur authentifié."""

    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False)

    user = relationship("User", back_populates="favorites")
    book = relationship("Book")


class ReadingProgress(Base):
    """Dernière page lue par un utilisateur pour un livre donné (reprise de lecture)."""

    __tablename__ = "reading_progress"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False, index=True)
    current_page = Column(Integer, default=1, nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    user = relationship("User", back_populates="reading_progress")
    book = relationship("Book")
