from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


# --- GENRES ---
class GenreBase(BaseModel):
    name: str


class GenreCreate(GenreBase):
    pass


class GenreResponse(GenreBase):
    id: int

    class Config:
        from_attributes = True


# --- CATEGORIES ---
class CategoryBase(BaseModel):
    name: str


class CategoryCreate(CategoryBase):
    pass


class CategoryResponse(CategoryBase):
    id: int

    class Config:
        from_attributes = True


# --- BOOKS ---
class BookBase(BaseModel):
    title: str
    author: str
    description: Optional[str] = None
    audio_url: Optional[str] = None


class BookResponse(BookBase):
    id: int
    pdf_filename: str
    cover_filename: Optional[str] = None
    view_count: int
    created_at: datetime
    genre: Optional[GenreResponse] = None
    category: Optional[CategoryResponse] = None

    class Config:
        from_attributes = True


# --- FAVORIS ---
class FavoriteResponse(BaseModel):
    id: int
    book_id: int
    user_id: int

    class Config:
        from_attributes = True


# --- PROGRESSION DE LECTURE ---
class ReadingProgressUpdate(BaseModel):
    current_page: int


class ReadingProgressResponse(BaseModel):
    book_id: int
    current_page: int
    updated_at: datetime

    class Config:
        from_attributes = True


# --- AUTHENTIFICATION ---
class UserCreate(BaseModel):
    email: str
    password: str
    display_name: Optional[str] = None


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    display_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
