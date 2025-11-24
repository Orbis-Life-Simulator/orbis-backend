from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from motor.motor_asyncio import AsyncIOMotorDatabase

from ..dependencies import get_db
from ..schemas import users as user_schemas
from ..schemas import token as token_schemas
from ..auth import get_password_hash, verify_password, create_access_token

router = APIRouter(prefix="/api/users", tags=["Users & Authentication"])


@router.post(
    "/register",
    response_model=user_schemas.UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_user(
    user: user_schemas.UserCreate, db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Registra um novo usuário no sistema."""

    existing_user = await db.users.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered."
        )

    hashed_password = get_password_hash(user.password)
    user_doc = {"email": user.email, "hashed_password": hashed_password}

    result = await db.users.insert_one(user_doc)
    created_user = await db.users.find_one({"_id": result.inserted_id})

    return created_user


@router.post("/login", response_model=token_schemas.Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Autentica um usuário e retorna um token de acesso."""

    user = await db.users.find_one({"email": form_data.username})
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user["email"]})
    return {"access_token": access_token, "token_type": "bearer"}
