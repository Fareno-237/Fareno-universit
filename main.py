from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, Integer, String, Time, Date, Boolean, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from passlib.context import CryptContext
import csv
from io import StringIO
import datetime
import random
from typing import List, Optional
import os

# Configuration
DATABASE_URL = "postgresql://fareno_university_db_user:fVBF3mIKs11vdYUYyXfRPaWk2Vu5b9SY@dpg-d1022abipnbc738ed7g0-a.oregon-postgres.render.com/fareno12"
engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
app = FastAPI()

# Monter la racine comme dossier statique pour servir les fichiers HTML
app.mount("/", StaticFiles(directory=".", html=True), name="root")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modèles SQLAlchemy
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True)
    email = Column(String(255), unique=True)
    password = Column(String(255))
    role = Column(String(50))

class Teacher(Base):
    __tablename__ = "teachers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255))
    email = Column(String(255))

class Group(Base):
    __tablename__ = "groups"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255))

class Room(Base):
    __tablename__ = "rooms"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255))

class Constraint(Base):
    __tablename__ = "constraints"
    id = Column(Integer, primary_key=True, index=True)
    resource_type = Column(String(50))
    resource_id = Column(Integer)
    resource_name = Column(String(255))
    day = Column(String(50))
    time = Column(Time)
    constraint_type = Column(String(50))

class Timetable(Base):
    __tablename__ = "timetable"
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer)
    teacher_id = Column(Integer)
    room_id = Column(Integer)
    subject = Column(String(255))
    day = Column(String(50))
    start_time = Column(Time)
    end_time = Column(Time)
    date = Column(Date)

# Modèles Pydantic
class LoginData(BaseModel):
    username: str
    password: str

class ConstraintCreate(BaseModel):
    resource_type: str
    resource_id: int
    resource_name: str
    day: str
    time: str
    constraint_type: str

class TimetableGenerate(BaseModel):
    group_id: int
    date: str

class TimetableEntry(BaseModel):
    group_id: int
    teacher_id: int
    room_id: int
    subject: str
    day: str
    start_time: str
    end_time: str
    date: str

# Dépendance pour la session DB
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Endpoints
@app.post("/api/login")
async def login(data: LoginData, db: Session = Depends(get_db)):
    query = text(
        "SELECT id FROM users WHERE (name = :username OR email = :username) AND password = crypt(:password, password)"
    )
    result = db.execute(query, {"username": data.username, "password": data.password}).fetchone()
    if result:
        return {"success": True}
    raise HTTPException(status_code=400, detail={"success": False, "error": "Identifiants incorrects"})

@app.get("/api/constraints")
async def get_constraints(db: Session = Depends(get_db)):
    constraints = db.query(Constraint).all()
    return [
        {
            "id": c.id,
            "resource_type": c.resource_type,
            "resource_id": c.resource_id,
            "resource_name": c.resource_name,
            "day": c.day,
            "time": c.time.strftime("%H:%M"),
            "constraint_type": c.constraint_type
        }
        for c in constraints
    ]

@app.post("/api/constraints")
async def add_constraint(constraint: ConstraintCreate, db: Session = Depends(get_db)):
    new_constraint = Constraint(
        resource_type=constraint.resource_type,
        resource_id=constraint.resource_id,
        resource_name=constraint.resource_name,
        day=constraint.day,
        time=datetime.datetime.strptime(constraint.time, "%H:%M").time(),
        constraint_type=constraint.constraint_type
    )
    db.add(new_constraint)
    db.commit()
    db.refresh(new_constraint)
    return {"id": new_constraint.id, "message": "Contrainte ajoutée avec succès"}

@app.get("/api/timetable")
async def get_timetable(
    search: Optional[str] = None,
    group_id: Optional[int] = None,
    teacher_id: Optional[int] = None,
    date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Timetable)
    if group_id:
        query = query.filter(Timetable.group_id == group_id)
    if teacher_id:
        query = query.filter(Timetable.teacher_id == teacher_id)
    if date:
        query = query.filter(Timetable.date == date)
    timetable = query.all()
    result = []
    for t in timetable:
        teacher = db.query(Teacher).filter(Teacher.id == t.teacher_id).first()
        room = db.query(Room).filter(Room.id == t.room_id).first()
        entry = {
            "id": t.id,
            "group_id": t.group_id,
            "teacher_id": t.teacher_id,
            "teacher_name": teacher.name if teacher else "",
            "room_id": t.room_id,
            "room_name": room.name if room else "",
            "subject": t.subject,
            "day": t.day,
            "start_time": t.start_time.strftime("%H:%M"),
            "end_time": t.end_time.strftime("%H:%M"),
            "date": t.date.strftime("%Y-%m-%d")
        }
        if search and search.lower() not in (entry["subject"].lower(), entry["teacher_name"].lower(), entry["room_name"].lower()):
            continue
        result.append(entry)
    return result

@app.get("/api/timetable/dates")
async def get_timetable_dates(db: Session = Depends(get_db)):
    dates = db.query(Timetable.date).distinct().all()
    return [d[0].strftime("%Y-%m-%d") for d in dates]

@app.post("/api/timetable/generate")
async def generate_timetable(data: TimetableGenerate, db: Session = Depends(get_db)):
    # Logique simple de génération
    group_id = data.group_id
    date = datetime.datetime.strptime(data.date, "%Y-%m-%d").date()
    days = ["lundi", "mardi", "mercredi", "jeudi", "vendredi"]
    time_slots = [
        {"start": "08:00", "end": "10:00"},
        {"start": "10:00", "end": "12:00"},
        {"start": "14:00", "end": "16:00"},
        {"start": "16:00", "end": "18:00"}
    ]
    subjects = ["Mathématiques", "Physique", "Chimie", "Biologie"]

    # Récupérer les ressources
    teachers = db.query(Teacher).all()
    rooms = db.query(Room).all()
    constraints = db.query(Constraint).filter(Constraint.resource_type == "teacher").all()

    # Supprimer les anciens emplois du temps pour ce groupe et cette date
    db.query(Timetable).filter(Timetable.group_id == group_id, Timetable.date == date).delete()
    db.commit()

    # Générer un emploi du temps
    for day in days:
        for slot in time_slots:
            # Vérifier les contraintes
            available_teachers = [t for t in teachers if not any(
                c.resource_id == t.id and c.day == day and c.time.strftime("%H:%M") == slot["start"]
                for c in constraints
            )]
            if not available_teachers:
                continue

            # Assigner aléatoirement
            teacher = random.choice(available_teachers)
            room = random.choice(rooms)
            subject = random.choice(subjects)

            new_entry = Timetable(
                group_id=group_id,
                teacher_id=teacher.id,
                room_id=room.id,
                subject=subject,
                day=day,
                start_time=datetime.datetime.strptime(slot["start"], "%H:%M").time(),
                end_time=datetime.datetime.strptime(slot["end"], "%H:%M").time(),
                date=date
            )
            db.add(new_entry)
    db.commit()
    return {"message": "Emploi du temps généré avec succès"}

@app.get("/api/timetable/export/{format}")
async def export_timetable(
    format: str,
    group_id: Optional[int] = None,
    teacher_id: Optional[int] = None,
    date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    timetable = await get_timetable(search=None, group_id=group_id, teacher_id=teacher_id, date=date, db=db)
    
    if format == "csv":
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["Jour", "Heure", "Sujet", "Enseignant", "Salle"])
        for entry in timetable:
            writer.writerow([
                entry["day"],
                f"{entry['start_time']} - {entry['end_time']}",
                entry["subject"],
                entry["teacher_name"],
                entry["room_name"]
            ])
        output.seek(0)
        return FileResponse(
            output,
            media_type="text/csv",
            filename="timetable.csv"
        )
    elif format in ["pdf", "ical"]:
        # Placeholder pour PDF et iCal (nécessite des bibliothèques supplémentaires)
        raise HTTPException(status_code=501, detail="Format non implémenté")
    raise HTTPException(status_code=400, detail="Format non supporté")

@app.get("/api/stats")
async def get_stats(db: Session = Depends(get_db)):
    timetables_count = db.query(Timetable).count()
    active_users = db.query(User).filter(User.last_login >= datetime.datetime.now() - datetime.timedelta(days=30)).count()
    conflicts_resolved = db.query(Constraint).filter(Constraint.constraint_type == "resolved").count()
    return {
        "timetables_generated": timetables_count,
        "active_users": active_users,
        "conflicts_resolved": conflicts_resolved
    }

@app.get("/api/groups")
async def get_groups(db: Session = Depends(get_db)):
    groups = db.query(Group).all()
    return [{"id": g.id, "name": g.name} for g in groups]

@app.get("/api/teachers")
async def get_teachers(db: Session = Depends(get_db)):
    teachers = db.query(Teacher).all()
    return [{"id": t.id, "name": t.name} for t in teachers]

# Créer les tables si elles n'existent pas
Base.metadata.create_all(bind=engine)