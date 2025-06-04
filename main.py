from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, Integer, String, Time, Date, Boolean, text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from passlib.context import CryptContext
import csv
from io import StringIO, BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors
from icalendar import Calendar, Event
from datetime import datetime, time, timedelta
import random
from typing import List, Optional
import os

# Configuration
DATABASE_URL = "postgresql://fareno_university_db_user:fVBF3mIKs11vdYUYyXfRPaWk2Vu5b9SY@dpg-d1022abibnbc738ed7g0-a.oregon-postgres.render.com/fareno_university_db?sslmode=require"
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
    last_login = Column(DateTime)

class Teacher(Base):
    __tablename__ = "teachers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255))
    email = Column(String(255))
    subjects = Column(String(255))
    availability = Column(String(255))
    is_active = Column(Boolean, default=True)

class Group(Base):
    __tablename__ = "groups"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255))
    student_count = Column(Integer)
    subjects = Column(String(255))
    is_active = Column(Boolean, default=True)

class Room(Base):
    __tablename__ = "rooms"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255))
    capacity = Column(Integer)
    equipment = Column(String(255))
    is_active = Column(Boolean, default=True)

class Constraint(Base):
    __tablename__ = "constraints"
    id = Column(Integer, primary_key=True, index=True)
    resource_type = Column(String(50))
    resource_id = Column(Integer)
    resource_name = Column(String(255))
    day = Column(String(50))
    time = Column(Time)
    constraint_type = Column(String(50))
    is_active = Column(Boolean, default=True)

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

class Log(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer)
    user_name = Column(String(255))
    action = Column(String(50))
    details = Column(String(255))

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

class TeacherCreate(BaseModel):
    name: str
    email: str
    subjects: str
    availability: str

class GroupCreate(BaseModel):
    name: str
    student_count: int
    subjects: str

class RoomCreate(BaseModel):
    name: str
    capacity: int
    equipment: str

class AdjustmentCreate(BaseModel):
    resource: str
    day: str
    time: str
    new_value: str

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

# Endpoints mis à jour pour inclure le logging
@app.post("/api/constraints")
async def add_constraint(constraint: ConstraintCreate, db: Session = Depends(get_db)):
    new_constraint = Constraint(**constraint.dict())
    db.add(new_constraint)
    db.commit()
    db.refresh(new_constraint)
    add_log(db, user_id=1, user_name="admin", action="create_constraint", details=f"Ajout de contrainte ID {new_constraint.id}")
    return {"id": new_constraint.id, "message": "Contrainte ajoutée avec succès"}

@app.put("/api/constraints/{constraint_id}")
async def update_constraint(constraint_id: int, constraint: ConstraintCreate, db: Session = Depends(get_db)):
    db_constraint = db.query(Constraint).filter(Constraint.id == constraint_id, Constraint.is_active == True).first()
    if not db_constraint:
        raise HTTPException(status_code=404, detail="Contrainte non trouvée")
    for key, value in constraint.dict().items():
        setattr(db_constraint, key, value)
    db.commit()
    add_log(db, user_id=1, user_name="admin", action="update_constraint", details=f"Mise à jour de contrainte ID {constraint_id}")
    return {"message": "Contrainte mise à jour avec succès"}

@app.delete("/api/constraints/{constraint_id}")
async def delete_constraint(constraint_id: int, db: Session = Depends(get_db)):
    db_constraint = db.query(Constraint).filter(Constraint.id == constraint_id, Constraint.is_active == True).first()
    if not db_constraint:
        raise HTTPException(status_code=404, detail="Contrainte non trouvée")
    db_constraint.is_active = False
    db.commit()
    add_log(db, user_id=1, user_name="admin", action="delete_constraint", details=f"Suppression logique de contrainte ID {constraint_id}")
    return {"message": "Contrainte marquée comme supprimée avec succès"}

@app.post("/api/teachers")
async def create_teacher(teacher: TeacherCreate, db: Session = Depends(get_db)):
    db_teacher = Teacher(**teacher.dict())
    db.add(db_teacher)
    db.commit()
    db.refresh(db_teacher)
    add_log(db, user_id=1, user_name="admin", action="create_teacher", details=f"Ajout d'enseignant ID {db_teacher.id}")
    return {"id": db_teacher.id, "message": "Enseignant ajouté avec succès"}

@app.put("/api/teachers/{teacher_id}")
async def update_teacher(teacher_id: int, teacher: TeacherCreate, db: Session = Depends(get_db)):
    db_teacher = db.query(Teacher).filter(Teacher.id == teacher_id, Teacher.is_active == True).first()
    if not db_teacher:
        raise HTTPException(status_code=404, detail="Enseignant non trouvé")
    for key, value in teacher.dict().items():
        setattr(db_teacher, key, value)
    db.commit()
    add_log(db, user_id=1, user_name="admin", action="update_teacher", details=f"Mise à jour d'enseignant ID {teacher_id}")
    return {"message": "Enseignant mis à jour avec succès"}

@app.delete("/api/teachers/{teacher_id}")
async def delete_teacher(teacher_id: int, db: Session = Depends(get_db)):
    db_teacher = db.query(Teacher).filter(Teacher.id == teacher_id, Teacher.is_active == True).first()
    if not db_teacher:
        raise HTTPException(status_code=404, detail="Enseignant non trouvé")
    db_teacher.is_active = False
    db.commit()
    add_log(db, user_id=1, user_name="admin", action="delete_teacher", details=f"Suppression logique d'enseignant ID {teacher_id}")
    return {"message": "Enseignant marqué comme supprimé avec succès"}

@app.post("/api/groups")
async def create_group(group: GroupCreate, db: Session = Depends(get_db)):
    db_group = Group(**group.dict())
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    add_log(db, user_id=1, user_name="admin", action="create_group", details=f"Ajout de groupe ID {db_group.id}")
    return {"id": db_group.id, "message": "Groupe ajouté avec succès"}

@app.put("/api/groups/{group_id}")
async def update_group(group_id: int, group: GroupCreate, db: Session = Depends(get_db)):
    db_group = db.query(Group).filter(Group.id == group_id, Group.is_active == True).first()
    if not db_group:
        raise HTTPException(status_code=404, detail="Groupe non trouvé")
    for key, value in group.dict().items():
        setattr(db_group, key, value)
    db.commit()
    add_log(db, user_id=1, user_name="admin", action="update_group", details=f"Mise à jour de groupe ID {group_id}")
    return {"message": "Groupe mis à jour avec succès"}

@app.delete("/api/groups/{group_id}")
async def delete_group(group_id: int, db: Session = Depends(get_db)):
    db_group = db.query(Group).filter(Group.id == group_id, Group.is_active == True).first()
    if not db_group:
        raise HTTPException(status_code=404, detail="Groupe non trouvé")
    db_group.is_active = False
    db.commit()
    add_log(db, user_id=1, user_name="admin", action="delete_group", details=f"Suppression logique de groupe ID {group_id}")
    return {"message": "Groupe marqué comme supprimé avec succès"}

@app.post("/api/rooms")
async def create_room(room: RoomCreate, db: Session = Depends(get_db)):
    db_room = Room(**room.dict())
    db.add(db_room)
    db.commit()
    db.refresh(db_room)
    add_log(db, user_id=1, user_name="admin", action="create_room", details=f"Ajout de salle ID {db_room.id}")
    return {"id": db_room.id, "message": "Salle ajoutée avec succès"}

@app.put("/api/rooms/{room_id}")
async def update_room(room_id: int, room: RoomCreate, db: Session = Depends(get_db)):
    db_room = db.query(Room).filter(Room.id == room_id, Room.is_active == True).first()
    if not db_room:
        raise HTTPException(status_code=404, detail="Salle non trouvée")
    for key, value in room.dict().items():
        setattr(db_room, key, value)
    db.commit()
    add_log(db, user_id=1, user_name="admin", action="update_room", details=f"Mise à jour de salle ID {room_id}")
    return {"message": "Salle mise à jour avec succès"}

@app.delete("/api/rooms/{room_id}")
async def delete_room(room_id: int, db: Session = Depends(get_db)):
    db_room = db.query(Room).filter(Room.id == room_id, Room.is_active == True).first()
    if not db_room:
        raise HTTPException(status_code=404, detail="Salle non trouvée")
    db_room.is_active = False
    db.commit()
    add_log(db, user_id=1, user_name="admin", action="delete_room", details=f"Suppression logique de salle ID {room_id}")
    return {"message": "Salle marquée comme supprimée avec succès"}

@app.post("/api/timetable/generate")
async def generate_timetable(data: TimetableGenerate, db: Session = Depends(get_db)):
    group_id = data.group_id
    date = datetime.strptime(data.date, "%Y-%m-%d").date()
    days = ["lundi", "mardi", "mercredi", "jeudi", "vendredi"]
    time_slots = [
        {"start": "08:00", "end": "10:00"},
        {"start": "10:00", "end": "12:00"},
        {"start": "14:00", "end": "16:00"},
        {"start": "16:00", "end": "18:00"}
    ]
    subjects = ["Mathématiques", "Physique", "Chimie", "Biologie"]

    teachers = db.query(Teacher).filter(Teacher.is_active == True).all()
    rooms = db.query(Room).filter(Room.is_active == True).all()
    constraints = db.query(Constraint).filter(Constraint.is_active == True, Constraint.resource_type == "teacher").all()

    db.query(Timetable).filter(Timetable.group_id == group_id, Timetable.date == date).delete()
    db.commit()

    for day in days:
        for slot in time_slots:
            available_teachers = [t for t in teachers if not any(
                c.resource_id == t.id and c.day == day and c.time.strftime("%H:%M") == slot["start"]
                for c in constraints
            )]
            if not available_teachers:
                continue

            teacher = random.choice(available_teachers)
            room = random.choice(rooms)
            subject = random.choice(subjects)

            new_entry = Timetable(
                group_id=group_id,
                teacher_id=teacher.id,
                room_id=room.id,
                subject=subject,
                day=day,
                start_time=datetime.strptime(slot["start"], "%H:%M").time(),
                end_time=datetime.strptime(slot["end"], "%H:%M").time(),
                date=date
            )
            db.add(new_entry)
    db.commit()
    add_log(db, user_id=1, user_name="admin", action="generate_timetable", details=f"Génération d'emploi du temps pour groupe ID {group_id} à la date {date}")
    return {"message": "Emploi du temps généré avec succès"}

# Nouveaux endpoints pour l'administration
@app.get("/api/logs")
async def get_logs(db: Session = Depends(get_db)):
    logs = db.query(Log).order_by(Log.date.desc()).all()
    return [
        {
            "id": log.id,
            "date": log.date.strftime("%Y-%m-%d %H:%M:%S"),
            "user": log.user_name,
            "action": log.action,
            "details": log.details
        }
        for log in logs
    ]

@app.post("/api/adjustments")
async def save_adjustments(adjustments: List[AdjustmentCreate], db: Session = Depends(get_db)):
    for adjustment in adjustments:
        teacher = db.query(Teacher).filter(Teacher.name == adjustment.resource, Teacher.is_active == True).first()
        group = db.query(Group).filter(Group.name == adjustment.resource, Group.is_active == True).first()

        if not teacher and not group:
            raise HTTPException(status_code=404, detail=f"Ressource {adjustment.resource} non trouvée")

        resource_type = "teacher" if teacher else "group"
        resource_id = teacher.id if teacher else group.id
        resource_name = adjustment.resource

        existing_constraint = db.query(Constraint).filter(
            Constraint.resource_type == resource_type,
            Constraint.resource_id == resource_id,
            Constraint.day == adjustment.day,
            Constraint.time == datetime.strptime(adjustment.time, "%H:%M").time(),
            Constraint.is_active == True
        ).first()

        if existing_constraint:
            existing_constraint.constraint_type = adjustment.new_value.lower()
            db.commit()
            add_log(db, user_id=1, user_name="admin", action="update_adjustment", details=f"Mise à jour de contrainte pour {resource_name} le {adjustment.day} à {adjustment.time}")
        else:
            new_constraint = Constraint(
                resource_type=resource_type,
                resource_id=resource_id,
                resource_name=resource_name,
                day=adjustment.day,
                time=datetime.strptime(adjustment.time, "%H:%M").time(),
                constraint_type=adjustment.new_value.lower(),
                is_active=True
            )
            db.add(new_constraint)
            db.commit()
            add_log(db, user_id=1, user_name="admin", action="create_adjustment", details=f"Création de contrainte pour {resource_name} le {adjustment.day} à {adjustment.time}")

    return {"message": "Ajustements appliqués avec succès"}

# Nouvel endpoint pour exécuter les migrations
@app.post("/api/migrate")
async def run_migration(db: Session = Depends(get_db)):
    try:
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login TIMESTAMP WITH TIME ZONE"))
        db.commit()
        return {"message": "Migration effectuée avec succès : colonne last_login ajoutée"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur lors de la migration : {str(e)}")

# Endpoints existants (non modifiés pour le logging ici pour brevité)
@app.get("/api/constraints")
async def get_constraints(db: Session = Depends(get_db)):
    constraints = db.query(Constraint).filter(Constraint.is_active == True).all()
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

@app.get("/api/teachers")
async def get_teachers(db: Session = Depends(get_db)):
    teachers = db.query(Teacher).filter(Teacher.is_active == True).all()
    return [{"id": t.id, "name": t.name, "email": t.email, "subjects": t.subjects, "availability": t.availability} for t in teachers]

@app.get("/api/groups")
async def get_groups(db: Session = Depends(get_db)):
    groups = db.query(Group).filter(Group.is_active == True).all()
    return [{"id": g.id, "name": g.name, "student_count": g.student_count, "subjects": g.subjects} for g in groups]

@app.get("/api/rooms")
async def get_rooms(db: Session = Depends(get_db)):
    rooms = db.query(Room).filter(Room.is_active == True).all()
    return [{"id": r.id, "name": r.name, "capacity": r.capacity, "equipment": r.equipment} for r in rooms]

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
        teacher = db.query(Teacher).filter(Teacher.id == t.teacher_id, Teacher.is_active == True).first()
        room = db.query(Room).filter(Room.id == t.room_id, Room.is_active == True).first()
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

@app.get("/api/timetable/export/{format}")
async def export_timetable(
    format: str,
    group_id: Optional[int] = None,
    teacher_id: Optional[int] = None,
    date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    timetable = await get_timetable(search=None, group_id=group_id, teacher_id=teacher_id, date=date, db=db)
    
    if not timetable:
        raise HTTPException(status_code=404, detail="Aucun emploi du temps disponible pour ces filtres")

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
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=timetable.csv"}
        )

    elif format == "pdf":
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        data = [["Jour", "Heure", "Sujet", "Enseignant", "Salle"]]
        for entry in timetable:
            data.append([
                entry["day"],
                f"{entry['start_time']} - {entry['end_time']}",
                entry["subject"],
                entry["teacher_name"],
                entry["room_name"]
            ])
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.green),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements = [table]
        doc.build(elements)
        buffer.seek(0)
        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=timetable.pdf"}
        )

    elif format == "ical":
        cal = Calendar()
        cal.add('prodid', '-//Fareno University//Timetable//EN')
        cal.add('version', '2.0')

        for entry in timetable:
            event = Event()
            event.add('summary', f"{entry['subject']} - {entry['teacher_name']}")
            event.add('location', entry['room_name'])

            date = datetime.strptime(entry['date'], "%Y-%m-%d")
            day_map = {"lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3, "vendredi": 4}
            days_to_add = day_map[entry['day'].lower()]
            event_date = date + timedelta(days=days_to_add)

            start_time = datetime.strptime(entry['start_time'], "%H:%M").time()
            end_time = datetime.strptime(entry['end_time'], "%H:%M").time()
            event.add('dtstart', datetime.combine(event_date, start_time))
            event.add('dtend', datetime.combine(event_date, end_time))
            event.add('dtstamp', datetime.now())
            cal.add_component(event)

        buffer = BytesIO()
        buffer.write(cal.to_ical())
        buffer.seek(0)
        return StreamingResponse(
            buffer,
            media_type="text/calendar",
            headers={"Content-Disposition": "attachment; filename=timetable.ics"}
        )

    raise HTTPException(status_code=400, detail="Format non supporté")

@app.get("/api/stats")
async def get_stats(db: Session = Depends(get_db)):
    timetables_count = db.query(Timetable).count()
    active_users = db.query(User).filter(User.last_login >= datetime.now() - timedelta(days=30)).count()
    conflicts_resolved = db.query(Constraint).filter(Constraint.constraint_type == "resolved", Constraint.is_active == True).count()
    return {
        "timetables_generated": timetables_count,
        "active_users": active_users,
        "conflicts_resolved": conflicts_resolved
    }

# Initialisation de la base de données avec un utilisateur admin et données de test
def init_db():
    db = SessionLocal()
    try:
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

# Initialiser les données uniquement si l'environnement est en mode développement/test
if os.getenv("ENVIRONMENT", "development") == "development":
    init_db()
