from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models
from schemas import StudentCreate, StudentResponse
from typing import List

router = APIRouter(prefix="/api/students", tags=["students"])

def student_to_response(s: models.Student) -> StudentResponse:
    return StudentResponse(
        id=str(s.id),
        registerNumber=s.register_number,
        name=s.name,
        gender=s.gender,
        department=s.department,
        status=s.status,
        currentShuttle=s.current_shuttle,
        currentSeat=s.current_seat,
        tripsToday=s.trips_today,
        totalDistance=round(s.total_distance, 2),
        totalFare=round(s.total_fare, 2),
        paymentStatus=s.active_payment_status,
        tripId=s.trip_id,
    )

@router.get("", response_model=List[StudentResponse])
def get_students(db: Session = Depends(get_db)):
    students = db.query(models.Student).order_by(models.Student.register_number).all()
    return [student_to_response(s) for s in students]

@router.get("/{register_number}", response_model=StudentResponse)
def get_student(register_number: str, db: Session = Depends(get_db)):
    s = db.query(models.Student).filter(
        models.Student.register_number == register_number
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="Student not found")
    return student_to_response(s)

@router.post("", response_model=StudentResponse)
def create_student(data: StudentCreate, db: Session = Depends(get_db)):
    existing = db.query(models.Student).filter(
        models.Student.register_number == data.register_number
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Student already exists")
    s = models.Student(
        register_number=data.register_number,
        name=data.name,
        gender=data.gender,
        department=data.department,
        fee_account=data.fee_account,
        payment_status=data.payment_status,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return student_to_response(s)
