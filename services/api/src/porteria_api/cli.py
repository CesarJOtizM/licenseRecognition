"""Comandos de administración: `python -m porteria_api.cli create-admin --username ana`.

Solo usan DatabaseSettings: crear el primer administrador no exige JWT_SECRET.
"""

import argparse
import getpass
import sys
from collections.abc import Callable, Sequence
from typing import TextIO

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from porteria_api.audit import USER_AUDIT_FIELDS, record_audit, snapshot
from porteria_api.config import DatabaseSettings
from porteria_api.db import create_db_engine
from porteria_api.models import AuditAction, User, UserRole
from porteria_api.schemas import UserCreate
from porteria_api.security import Passwords

EXIT_REJECTED = 1  # entrada inválida, contraseñas distintas o usuario repetido
EXIT_DB_UNAVAILABLE = 3  # 2 lo usa argparse para errores de uso


class CliError(Exception):
    def __init__(self, message: str, exit_code: int = EXIT_REJECTED) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def create_admin(
    session: Session, passwords: Passwords, *, username: str, full_name: str, password: str
) -> User:
    """Crea un admin activo y su fila `user.created` sin actor, en una sola transacción."""
    user = User(
        username=username,
        password_hash=passwords.hash(password),
        full_name=full_name,
        role=UserRole.ADMIN,
    )
    try:
        with session.begin_nested():
            session.add(user)
    except IntegrityError as exc:
        if getattr(getattr(exc.orig, "diag", None), "constraint_name", None) == "uq_users_username":
            raise CliError(f"el usuario '{username}' ya existe") from None
        raise
    record_audit(
        session,
        actor=None,
        action=AuditAction.USER_CREATED,
        entity_type="user",
        entity_id=user.id,
        after=snapshot(user, USER_AUDIT_FIELDS),
    )
    session.commit()
    return user


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m porteria_api.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create-admin", help="crea un usuario administrador")
    create.add_argument("--username", required=True)
    create.add_argument("--full-name", default="Administrador")
    create.add_argument(
        "--password-stdin",
        action="store_true",
        help="lee la contraseña de la primera línea de la entrada estándar (sin confirmación)",
    )
    return parser


def _read_password(args: argparse.Namespace, read: Callable[[str], str], stdin: TextIO) -> str:
    if args.password_stdin:
        return stdin.readline().rstrip("\r\n")
    password = read("Contraseña: ")
    if read("Repite la contraseña: ") != password:
        raise CliError("las contraseñas no coinciden")
    return password


def _validate(args: argparse.Namespace, password: str) -> UserCreate:
    """Las mismas reglas de `POST /users`; los mensajes no incluyen lo que se escribió."""
    try:
        return UserCreate(
            username=args.username,
            password=password,
            full_name=args.full_name,
            role=UserRole.ADMIN,
        )
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(map(str, error['loc']))}: {error['msg']}"
            for error in exc.errors(include_input=False, include_url=False)
        )
        raise CliError(details) from None


def _create(data: UserCreate, session: Session | None, passwords: Passwords) -> User:
    fields = {"username": data.username, "full_name": data.full_name, "password": data.password}
    if session is not None:
        return create_admin(session, passwords, **fields)
    engine = create_db_engine(DatabaseSettings())
    try:
        # Sin expirar al confirmar: `main` lee username e id con la sesión ya cerrada.
        with Session(engine, expire_on_commit=False) as own_session:
            return create_admin(own_session, passwords, **fields)
    finally:
        engine.dispose()


def main(
    argv: Sequence[str] | None = None,
    *,
    read_password: Callable[[str], str] = getpass.getpass,
    stdin: TextIO | None = None,
    session: Session | None = None,
    passwords: Passwords | None = None,
) -> int:
    args = _parser().parse_args(argv)
    try:
        password = _read_password(args, read_password, stdin or sys.stdin)
        data = _validate(args, password)
        try:
            user = _create(data, session, passwords or Passwords())
        except OperationalError as exc:
            # Solo el error del driver: el de SQLAlchemy puede traer la sentencia y sus parámetros.
            message = f"no se pudo conectar a la base de datos: {exc.orig}"
            raise CliError(message, EXIT_DB_UNAVAILABLE) from None
    except CliError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return exc.exit_code
    print(f"Administrador '{user.username}' creado (id {user.id}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
