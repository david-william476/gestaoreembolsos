import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from sqlalchemy.orm import Session, joinedload
from .config import ACCESS_TOKEN_MINUTES, JWT_ALGORITHM, JWT_SECRET_KEY
from .database import get_db
from .models import User

# O FastAPI usa esse esquema para solicitar e validar o token Bearer.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def hash_password(senha: str) -> str:
    """Protege a senha com salt individual antes de guardá-la no banco."""
    sal = secrets.token_bytes(16)
    hash_calculado = hashlib.pbkdf2_hmac("sha256", senha.encode(), sal, 310_000)
    return f"pbkdf2_sha256$310000${sal.hex()}${hash_calculado.hex()}"


def verify_password(senha: str, hash_armazenado: str) -> bool:
    """Compara a senha informada com o hash armazenado."""
    try:
        formato, iteracoes, sal_hex, hash_hex = hash_armazenado.split("$")
        if formato != "pbkdf2_sha256":
            return False
        hash_calculado = hashlib.pbkdf2_hmac("sha256", senha.encode(), bytes.fromhex(sal_hex), int(iteracoes))
        return hmac.compare_digest(hash_calculado.hex(), hash_hex)
    except (ValueError, TypeError):
        return False


def create_access_token(usuario: User) -> str:
    """Emite um token de acesso com prazo de validade limitado."""
    agora = datetime.now(timezone.utc)
    dados_token = {"sub": str(usuario.id), "iat": agora, "exp": agora + timedelta(minutes=ACCESS_TOKEN_MINUTES)}
    return jwt.encode(dados_token, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def get_current_user(token_acesso: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """Valida a sessão e carrega o perfil atual diretamente do banco."""
    erro_nao_autorizado = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas ou sessão expirada", headers={"WWW-Authenticate": "Bearer"})
    try:
        dados_token = jwt.decode(token_acesso, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM], options={"require": ["sub", "exp"]})
        usuario_id = int(dados_token["sub"])
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        raise erro_nao_autorizado
    usuario = db.query(User).options(joinedload(User.department)).filter(User.id == usuario_id).first()
    if usuario is None or not usuario.active:
        raise erro_nao_autorizado
    return usuario


def require_roles(*perfis: str):
    """Cria uma verificação reutilizável para rotas de perfis específicos."""
    def verificar_perfil(usuario: User = Depends(get_current_user)) -> User:
        if usuario.role not in perfis:
            raise HTTPException(status_code=403, detail="Você não tem permissão para esta operação")
        return usuario
    return verificar_perfil
