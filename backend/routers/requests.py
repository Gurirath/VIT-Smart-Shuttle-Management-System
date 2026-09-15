from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models
from schemas import ShuttleRequestCreate, ShuttleRequestResponse
from typing import List
from datetime import datetime, timezone

router = APIRouter(prefix="/api/requests", tags=["requests"])

def request_to_response(r: models.ShuttleRequest) -> ShuttleRequestResponse:
    return ShuttleRequestResponse(
        id=r.request_id,
        studentId=r.student_id,
        studentName=r.student_name,
        pickupStop=r.pickup_stop,
        destinationStop=r.destination_stop,
        classEndTime=r.class_end_time,
        requestTime=r.created_at.isoformat() if r.created_at else datetime.now(timezone.utc).isoformat(),
        status=r.status,
    )

@router.get("", response_model=List[ShuttleRequestResponse])
def get_requests(db: Session = Depends(get_db)):
    reqs = db.query(models.ShuttleRequest).order_by(models.ShuttleRequest.id.desc()).all()
    return [request_to_response(r) for r in reqs]

@router.post("", response_model=ShuttleRequestResponse)
def create_request(data: ShuttleRequestCreate, db: Session = Depends(get_db)):
    student = db.query(models.Student).filter(
        models.Student.register_number == data.student_id
    ).first()
    student_name = student.name if student else data.student_id
    
    count = db.query(models.ShuttleRequest).count()
    request_id = f"REQ-{str(count + 1).zfill(3)}"
    
    req = models.ShuttleRequest(
        request_id=request_id,
        student_id=data.student_id,
        student_name=student_name,
        pickup_stop=data.pickup_stop,
        destination_stop=data.destination_stop,
        class_end_time=data.class_end_time,
        status="PENDING",
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return request_to_response(req)

@router.post("/{request_id}/assign")
def assign_request(request_id: str, db: Session = Depends(get_db)):
    req = db.query(models.ShuttleRequest).filter(
        models.ShuttleRequest.request_id == request_id
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    req.status = "ASSIGNED"
    db.commit()
    return {"message": f"Request {request_id} assigned"}
