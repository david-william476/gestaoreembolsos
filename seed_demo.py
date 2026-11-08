from app.config import DATABASE_URL
from app.database import Base, build_engine, make_session_factory
from app.models import Department, User
from app.security import hash_password


def seed():
    engine = build_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    factory = make_session_factory(engine)
    with factory() as db:
        departments = {
            name: db.query(Department).filter_by(name=name).first() or Department(name=name)
            for name in ("Comercial", "Tecnologia", "Financeiro")
        }
        db.add_all(departments.values())
        db.commit()
        for department in departments.values():
            db.refresh(department)
        # Contas didáticas usadas nos exemplos e nos testes; mantenha seus dados estáveis.
        demo_users = [
            ("Ana Silva", "ana@nexuscorp.com", "Ana123!", "colaborador", "Comercial"),
            ("Bruno Lima", "bruno@nexuscorp.com", "Bruno123!", "colaborador", "Tecnologia"),
            ("Patrícia Souza", "patricia@nexuscorp.com", "Patricia123!", "gestor", "Comercial"),
            ("Marcos Costa", "marcos@nexuscorp.com", "Marcos123!", "gestor", "Tecnologia"),
            ("Fernanda Alves", "fernanda@nexuscorp.com", "Fernanda123!", "financeiro", "Financeiro"),
        ]
        for name, email, password, role, department_name in demo_users:
            user = db.query(User).filter_by(email=email).first()
            if user is None:
                db.add(User(name=name, email=email, password_hash=hash_password(password), role=role, department_id=departments[department_name].id, active=True))
        db.commit()
    print("Base inicializada. Contas de demonstração:")
    for _, email, password, role, _ in demo_users:
        print(f"{role:12} {email:26} senha: {password}")


if __name__ == "__main__":
    seed()
