# ... (les imports et configurations précédents restent inchangés)

# Modèles SQLAlchemy
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True)
    email = Column(String(255), unique=True)
    password = Column(String(255))
    role = Column(String(50))
    last_login = Column(DateTime)

# ... (les autres modèles comme Teacher, Group, Room, Constraint, Timetable, Log restent inchangés)

# Dépendance pour la session DB
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Fonction utilitaire pour ajouter un log
def add_log(db: Session, user_id: int, user_name: str, action: str, details: str):
    new_log = Log(
        user_id=user_id,
        user_name=user_name,
        action=action,
        details=details
    )
    db.add(new_log)
    db.commit()

# ... (les autres endpoints restent inchangés)

# Initialisation de la base de données avec un utilisateur admin et données de test
def init_db():
    db = SessionLocal()
    try:
        # Vérifier et ajouter la colonne last_login si elle n'existe pas
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login TIMESTAMP WITH TIME ZONE"))
        db.commit()

        user_count = db.query(User).count()
        if user_count == 0:
            admin = User(
                name="admin",
                email="admin@gmail.com",
                password=pwd_context.hash("Fareno12"),
                role="admin"
            )
            db.add(admin)
            db.commit()
            print("Utilisateur admin créé.")

        if db.query(Teacher).count() == 0:
            teachers = [
                Teacher(name="M. Dupont", email="dupont@email.com", subjects="Mathématiques", availability="Lundi 08:00-12:00"),
                Teacher(name="Mme Lefèvre", email="lefevre@email.com", subjects="Physique", availability="Mardi 14:00-18:00")
            ]
            db.add_all(teachers)
            db.commit()
            print("Enseignants test ajoutés.")

        if db.query(Group).count() == 0:
            groups = [
                Group(name="Groupe A", student_count=30, subjects="Mathématiques, Physique"),
                Group(name="Groupe B", student_count=25, subjects="Chimie, Biologie")
            ]
            db.add_all(groups)
            db.commit()
            print("Groupes test ajoutés.")

        if db.query(Room).count() == 0:
            rooms = [
                Room(name="Salle 101", capacity=40, equipment="Projecteur, Tableau"),
                Room(name="Salle 102", capacity=30, equipment="Ordinateurs")
            ]
            db.add_all(rooms)
            db.commit()
            print("Salles test ajoutées.")

        if db.query(Constraint).count() == 0:
            constraints = [
                Constraint(resource_type="teacher", resource_id=1, resource_name="M. Dupont", day="lundi", time=time(8, 0), constraint_type="unavailable"),
                Constraint(resource_type="teacher", resource_id=2, resource_name="Mme Lefèvre", day="mardi", time=time(14, 0), constraint_type="preference")
            ]
            db.add_all(constraints)
            db.commit()
            print("Contraintes test ajoutées.")
    finally:
        db.close()

# Créer les tables si elles n'existent pas
Base.metadata.create_all(bind=engine)
init_db()
