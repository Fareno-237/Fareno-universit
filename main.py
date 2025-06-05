from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, Integer, String, Time, Date, Boolean, DateTime
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
import os
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database connection
DATABASE_URL = "postgresql://neondb_owner:npg_IjbgPtSNO6H8@ep-steep-hat-a8yxx3sa-pooler.eastus2.azure.neon.tech/neondb?sslmode=require"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()
pwd_context = CryptContext(schemes=["bcrypt"])

# FastAPI app setup
app = FastAPI()
app.mount("/", StaticFiles(directory=".", html=True), name="root")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Database models
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True)
    email = Column(String(255), unique=True)
    password = Column(String(255))
    role = Column(String(50))
    last_login = Column(DateTime)

class Teacher(Base):
    __tablename__ = "teachers"
    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    email = Column(String(255))
    subjects = Column(String(255))
    availability = Column(String(255))
    is_active = Column(Boolean, default=True)

class Group(Base):
    __tablename__ = "groups"
    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    student_count = Column(Integer)
    subjects = Column(String(255))
    is_active = Column(Boolean, default=True)

class Room(Base):
    __tablename__ = "rooms"
    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    capacity = Column(Integer)
    equipment = Column(String(255))
    is_active = Column(Boolean, default=True)

class Constraint(Base):
    __tablename__ = "constraints"
    id = Column(Integer, primary_key=True)
    resource_type = Column(String(50))
    resource_id = Column(Integer)
    resource_name = Column(String(255))
    day = Column(String(50))
    time = Column(Time)
    constraint_type = Column(String(50))
    is_active = Column(Boolean, default=True)

class Timetable(Base):
    __tablename__ = "timetable"
    id = Column(Integer, primary_key=True)
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
    id = Column(Integer, primary_key=True)
    date = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer)
    user_name = Column(String(255))
    action = Column(String(50))
    details = Column(String(255))

# Pydantic models
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

# Database session dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Logging helper
def log_action(db: Session, user_id: int, user_name: str, action: str, details: str):
    log = Log(user_id=user_id, user_name=user_name, action=action, details=details)
    db.add(log)
    db.commit()

# API endpoints
@app.post("/api/constraints")
async def add_constraint(constraint: ConstraintCreate, db: Session = Depends(get_db)):
    new_constraint = Constraint(**constraint.dict())
    db.add(new_constraint)
    db.commit()
    db.refresh(new_constraint)
    log_action(db, 1, "admin", "create_constraint", f"Added constraint ID {new_constraint.id}")
    return {"id": new_constraint.id, "message": "Constraint added"}

@app.put("/api/constraints/{constraint_id}")
async def update_constraint(constraint_id: int, constraint: ConstraintCreate, db: Session = Depends(get_db)):
    db_constraint = db.query(Constraint).filter(Constraint.id == constraint_id, Constraint.is_active == True).first()
    if not db_constraint:
        raise HTTPException(status_code=404, detail="Constraint not found")
    for key, value in constraint.dict().items():
        setattr(db_constraint, key, value)
    db.commit()
    log_action(db, 1, "admin", "update_constraint", f"Updated constraint ID {constraint_id}")
    return {"message": "Constraint updated"}

@app.delete("/api/constraints/{constraint_id}")
async def delete_constraint(constraint_id: int, db: Session = Depends(get_db)):
    db_constraint = db.query(Constraint).filter(Constraint.id == constraint_id, Constraint.is_active == True).first()
    if not db_constraint:
        raise HTTPException(status_code=404, detail="Constraint not found")
    db_constraint.is_active = False
    db.commit()
    log_action(db, 1, "admin", "delete_constraint", f"Deleted constraint ID {constraint_id}")
    return {"message": "Constraint deleted"}

@app.post("/api/teachers")
async def create_teacher(teacher: TeacherCreate, db: Session = Depends(get_db)):
    new_teacher = Teacher(**teacher.dict())
    db.add(new_teacher)
    db.commit()
    db.refresh(new_teacher)
    log_action(db, 1, "admin", "create_teacher", f"Added teacher ID {new_teacher.id}")
    return {"id": new_teacher.id, "message": "Teacher added"}

@app.put("/api/teachers/{teacher_id}")
async def update_teacher(teacher_id: int, teacher: TeacherCreate, db: Session = Depends(get_db)):
    db_teacher = db.query(Teacher).filter(Teacher.id == teacher_id, Teacher.is_active == True).first()
    if not db_teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    for key, value in teacher.dict().items():
        setattr(db_teacher, key, value)
    db.commit()
    log_action(db, 1, "admin", "update_teacher", f"Updated teacher ID {teacher_id}")
    return {"message": "Teacher updated"}

@app.delete("/api/teachers/{teacher_id}")
async def delete_teacher(teacher_id: int, db: Session = Depends(get_db)):
    db_teacher = db.query(Teacher).filter(Teacher.id == teacher_id, Teacher.is_active == True).first()
    if not db_teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    db_teacher.is_active = False
    db.commit()
    log_action(db, 1, "admin", "delete_teacher", f"Deleted teacher ID {teacher_id}")
    return {"message": "Teacher deleted"}

@app.post("/api/groups")
async def create_group(group: GroupCreate, db: Session = Depends(get_db)):
    new_group = Group(**group.dict())
    db.add(new_group)
    db.commit()
    db.refresh(new_group)
    log_action(db, 1, "admin", "create_group", f"Added group ID {new_group.id}")
    return {"id": new_group.id, "message": "Group added"}

@app.put("/api/groups/{group_id}")
async def update_group(group_id: int, group: GroupCreate, db: Session = Depends(get_db)):
    db_group = db.query(Group).filter(Group.id == group_id, Group.is_active == True).first()
    if not db_group:
        raise HTTPException(status_code=404, detail="Group not found")
    for key, value in group.dict().items():
        setattr(db_group, key, value)
    db.commit()
    log_action(db, 1, "admin", "update_group", f"Updated group ID {group_id}")
    return {"message": "Group updated"}

@app.delete("/api/groups/{group_id}")
async def delete_group(group_id: int, db: Session = Depends(get_db)):
    db_group = db.query(Group).filter(Group.id == group_id, Group.is_active == True).first()
    if not db_group:
        raise HTTPException(status_code=404, detail="Group not found")
    db_group.is_active = False
    db.commit()
    log_action(db, 1, "admin", "delete_group", f"Deleted group ID {group_id}")
    return {"message": "Group deleted"}

@app.post("/api/rooms")
async def create_room(room: RoomCreate, db: Session = Depends(get_db)):
    new_room = Room(**room.dict())
    db.add(new_room)
    db.commit()
    db.refresh(new_room)
    log_action(db, 1, "admin", "create_room", f"Added room ID {new_room.id}")
    return {"id": new_room.id, "message": "Room added"}

@app.put("/api/rooms/{room_id}")
async def update_room(room_id: int, room: RoomCreate, db: Session = Depends(get_db)):
    db_room = db.query(Room).filter(Room.id == room_id, Room.is_active == True).first()
    if not db_room:
        raise HTTPException(status_code=404, detail="Room not found")
    for key, value in room.dict().items():
        setattr(db_room, key, value)
    db.commit()
    log_action(db, 1, "admin", "update_room", f"Updated room ID {room_id}")
    return {"message": "Room updated"}

@app.delete("/api/rooms/{room_id}")
async def delete_room(room_id: int, db: Session = Depends(get_db)):
    db_room = db.query(Room).filter(Room.id == room_id, Room.is_active == True).first()
    if not db_room:
        raise HTTPException(status_code=404, detail="Room not found")
    db_room.is_active = False
    db.commit()
    log_action(db, 1, "admin", "delete_room", f"Deleted room ID {room_id}")
    return {"message": "Room deleted"}

@app.post("/api/timetable/generate")
async def generate_timetable(data: TimetableGenerate, db: Session = Depends(get_db)):
    group_id = data.group_id
    date = datetime.strptime(data.date, "%Y-%m-%d").date()
    days = ["lundi", "mardi", "mercredi", "jeudi", "vendredi"]
    time_slots = [{"start": "08:00", "end": "10:00"}, {"start": "10:00", "end": "12:00"}, {"start": "14:00", "end": "16:00"}, {"start": "16:00", "end": "18:00"}]
    subjects = ["Mathématiques", "Physique", "Chimie", "Biologie"]

    teachers = db.query(Teacher).filter(Teacher.is_active == True).all()
    rooms = db.query(Room).filter(Room.is_active == True).all()
    constraints = db.query(Constraint).filter(Constraint.is_active == True, Constraint.resource_type == "teacher").all()

    db.query(Timetable).filter(Timetable.group_id == group_id, Timetable.date == date).delete()
    db.commit()

    for day in days:
        for slot in time_slots:
            available_teachers = [t for t in teachers if not any(c.resource_id == t.id and c.day == day and c.time.strftime("%H:%M") == slot["start"] for c in constraints)]
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
    log_action(db, 1, "admin", "generate_timetable", f"Generated timetable for group ID {group_id} on {date}")
    return {"message": "Timetable generated"}

@app.get("/api/logs")
async def get_logs(db: Session = Depends(get_db)):
    logs = db.query(Log).order_by(Log.date.desc()).all()
    return [{"id": log.id, "date": log.date.strftime("%Y-%m-%d %H:%M:%S"), "user": log.user_name, "action": log.action, "details": log.details} for log in logs]

@app.post("/api/adjustments")
async def save_adjustments(adjustments: list[AdjustmentCreate], db: Session = Depends(get_db)):
    for adj in adjustments:
        teacher = db.query(Teacher).filter(Teacher.name == adj.resource, Teacher.is_active == True).first()
        group = db.query(Group).filter(Group.name == adj.resource, Group.is_active == True).first()
        if not teacher and not group:
            raise HTTPException(status_code=404, detail=f"Resource {adj.resource} not found")
        resource_type = "teacher" if teacher else "group"
        resource_id = teacher.id if teacher else group.id
        resource_name = adj.resource
        existing = db.query(Constraint).filter(Constraint.resource_type == resource_type, Constraint.resource_id == resource_id, Constraint.day == adj.day, Constraint.time == datetime.strptime(adj.time, "%H:%M").time(), Constraint.is_active == True).first()
        if existing:
            existing.constraint_type = adj.new_value.lower()
            db.commit()
            log_action(db, 1, "admin", "update_adjustment", f"Updated constraint for {resource_name} on {adj.day} at {adj.time}")
        else:
            new_constraint = Constraint(resource_type=resource_type, resource_id=resource_id, resource_name=resource_name, day=adj.day, time=datetime.strptime(adj.time, "%H:%M").time(), constraint_type=adj.new_value.lower(), is_active=True)
            db.add(new_constraint)
            db.commit()
            log_action(db, 1, "admin", "create_adjustment", f"Created constraint for {resource_name} on {adj.day} at {adj.time}")
    return {"message": "Adjustments applied"}

@app.post("/api/migrate")
async def run_migration(db: Session = Depends(get_db)):
    try:
        db.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login TIMESTAMP WITH TIME ZONE")
        db.commit()
        return {"message": "Migration completed: last_login column added"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Migration error: {str(e)}")

@app.get("/api/constraints")
async def get_constraints(db: Session = Depends(get_db)):
    constraints = db.query(Constraint).filter(Constraint.is_active == True).all()
    return [{"id": c.id, "resource_type": c.resource_type, "resource_id": c.resource_id, "resource_name": c.resource_name, "day": c.day, "time": c.time.strftime("%H:%M"), "constraint_type": c.constraint_type} for c in constraints]

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
async def get_timetable(search: str | None = None, group_id: int | None = None, teacher_id: int | None = None, date: str | None = None, db: Session = Depends(get_db)):
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
async def export_timetable(format: str, group_id: int | None = None, teacher_id: int | None = None, date: str | None = None, db: Session = Depends(get_db)):
    timetable = await get_timetable(search=None, group_id=group_id, teacher_id=teacher_id, date=date, db=db)
    if not timetable:
        raise HTTPException(status_code=404, detail="No timetable available")
    if format == "csv":
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["Day", "Time", "Subject", "Teacher", "Room"])
        for entry in timetable:
            writer.writerow([entry["day"], f"{entry['start_time']} - {entry['end_time']}", entry["subject"], entry["teacher_name"], entry["room_name"]])
        output.seek(0)
        return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=timetable.csv"})
    elif format == "pdf":
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        data = [["Day", "Time", "Subject", "Teacher", "Room"]]
        for entry in timetable:
            data.append([entry["day"], f"{entry['start_time']} - {entry['end_time']}", entry["subject"], entry["teacher_name"], entry["room_name"]])
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
        doc.build([table])
        buffer.seek(0)
        return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=timetable.pdf"})
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
        return StreamingResponse(buffer, media_type="text/calendar", headers={"Content-Disposition": "attachment; filename=timetable.ics"})
    raise HTTPException(status_code=400, detail="Unsupported format")

@app.get("/api/stats")
async def get_stats(db: Session = Depends(get_db)):
    return {
        "timetables_generated": db.query(Timetable).count(),
        "active_users": db.query(User).filter(User.last_login >= datetime.now() - timedelta(days=30)).count(),
        "conflicts_resolved": db.query(Constraint).filter(Constraint.constraint_type == "resolved", Constraint.is_active == True).count()
    }

# Initialize database with test data
def init_db():
    db = SessionLocal()
    try:
        if not db.query(User).count():
            admin = User(name="admin", email="admin@gmail.com", password=pwd_context.hash("Fareno12"), role="admin")
            db.add(admin)
            db.commit()
        if not db.query(Teacher).count():
            teachers = [
                Teacher(name="M. Dupont", email="dupont@email.com", subjects="Mathématiques", availability="Lundi 08:00-12:00"),
                Teacher(name="Mme Lefèvre", email="lefevre@email.com", subjects="Physique", availability="Mardi 14:00-18:00")
            ]
            db.add_all(teachers)
            db.commit()
        if not db.query(Group).count():
            groups = [
                Group(name="Groupe A", student_count=30, subjects="Mathématiques, Physique"),
                Group(name="Groupe B", student_count=25, subjects="Chimie, Biologie")
            ]
            db.add_all(groups)
            db.commit()
        if not db.query(Room).count():
            rooms = [
                Room(name="Salle 101", capacity=40, equipment="Projecteur, Tableau"),
                Room(name="Salle 102", capacity=30, equipment="Ordinateurs")
            ]
            db.add_all(rooms)
            db.commit()
        if not db.query(Constraint).count():
            constraints = [
                Constraint(resource_type="teacher", resource_id=1, resource_name="M. Dupont", day="lundi", time=time(8, 0), constraint_type="unavailable"),
                Constraint(resource_type="teacher", resource_id=2, resource_name="Mme Lefèvre", day="mardi", time=time(14, 0), constraint_type="preference")
            ]
            db.add_all(constraints)
            db.commit()
    finally:
        db.close()

# Create tables and initialize data
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    logger.error(f"Table creation error: {str(e)}")
if os.getenv("ENVIRONMENT", "development") == "development":
    try:
        init_db()
    except Exception as e:
        logger.error(f"Data initialization error: {str(e)}")
