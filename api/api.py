from collections import OrderedDict
from typing import List
from hash import *
from mkclaims import *

import contextlib
import logging.config
import sqlite3
import datetime
import random

from fastapi import FastAPI, Depends, Response, Request, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from pydantic_settings import BaseSettings

class Register(BaseModel):
    username: str
    password: str
    roles: List[str]

class Login(BaseModel):
    username: str
    password: str    

class Settings(BaseSettings, env_file=".env", extra="ignore"):
    database: str                                               
    secondary: str       #Added more database variables to access the replica db
    secondary2:str
    logging_config: str

def getPrimary_db():
     with contextlib.closing(sqlite3.connect(settings.database)) as db:
        db.row_factory = sqlite3.Row
        yield db

def getSecondary_db():
    with contextlib.closing(sqlite3.connect(random.choice([settings.secondary,settings.secondary2]))) as db:
            db.row_factory = sqlite3.Row
            yield db

def get_logger():
    return logging.getLogger(__name__)

settings = Settings()
app = FastAPI()

logging.config.fileConfig(settings.logging_config, disable_existing_loggers=False)

# ---------------------- Tasks -----------------------------

# Task 1: Registering a student
# Example: POST http://localhost:5000/register
@app.post("/register")
def register_user(register: Register, request: Request, db: sqlite3.Connection = Depends(getPrimary_db)):
        reg_user = dict(register)
        check_username = db.execute("SELECT * FROM USER WHERE username=?", (reg_user["username"],))  #Accepts a tuple as Input for Sql queries
        
        # if the username exists, then return 409.    
        if check_username.fetchone():             #check username gives out an SQL object need to fetch value from that object, value could be "None" or a record
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username taken."
            )
        
        hash_pw = hash_password(reg_user["password"])

        # Inserting registered user to database.
        db.execute("""
            INSERT INTO User (username, password)
            VALUES (?,?)
        """, (reg_user['username'], hash_pw)) #Corrected the query

        for role in reg_user["roles"]:
             db.execute("""
                INSERT INTO Roles (r_username, role)
                VALUES (?,?)
                        """, (reg_user["username"], role)) # will create Separate entries for different roles of Same username

        db.commit()

        return {"data": "Person added woo ^-^"}

# Example: POST http://localhost:5000/login
# STATUS: COMPLETE
@app.post("/login")
def login_user(login: Login, request: Request, db: sqlite3.Connection = Depends(getSecondary_db)):
    user = dict(login)
    #authenticating user
    fetch_user = db.execute("SELECT * FROM USER WHERE username= ?",(user['username'],)) #will return None if user doesnt exist
    userDetails = fetch_user.fetchone() #Willgive a SQL Object need to fecth password and username from it

    if not userDetails:             # Checks for correct login.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invalid login Credentials."
        )
    
    password = userDetails[1]
    
    passVer = verify_password(user['password'], password)
    if not passVer:  #if passVer evaluates to false this will raise Conflict
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invalid login Credentials."
        )
    #need to fetch user role for generating claims

    fetch_role = db.execute("Select * FROM ROLES WHERE r_username=?", (user["username"],))
    roleDetails = fetch_role.fetchone()
    claims = generate_claims(user['username'], None, roleDetails[1])

    return claims

# Endpoint to test validation. 
@app.get("/AdminsOnly")
def admin_check():
    return {"data": "This page is the cool kids club. Only Admins allowed yo!"}





# ---------------------- Add Project 1 -----------------------------


class Enrollment(BaseModel):
    StudentId: int
    ClassId: int

class Class(BaseModel):
    InstructorId: int
    Department: str
    CourseCode: str
    SectionNumber: int
    ClassName: str
    MaxEnrollment: int = 40
    AutomaticEnrollmentFrozen: int = 0

class UpdateInstructor(BaseModel):
    InstructorId: int

def get_db():
    with contextlib.closing(sqlite3.connect("project1.db")) as db:
        db.row_factory = sqlite3.Row
        yield db

@app.get("/",status_code=status.HTTP_308_PERMANENT_REDIRECT)
def default():
    return RedirectResponse("/docs")

"""
API for Students Endpoints
"""

# It lists the available classes to students
@app.get("/classes", status_code=status.HTTP_200_OK)
def list_available_classes(db: sqlite3.Connection = Depends(get_db)):
    classes = db.execute("SELECT * FROM classes where CurrentEnrollment < MaxEnrollment")
    if not classes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Classes not found"
        )
    return {"Classes": classes.fetchall()}


# To enroll in a class
@app.post("/enrollments/", status_code=status.HTTP_201_CREATED)
def create_enrollment(
    enrollment: Enrollment, response: Response, db: sqlite3.Connection = Depends(get_db)
):
    cur = db.execute("select CurrentEnrollment, MaxEnrollment, AutomaticEnrollmentFrozen from Classes where ClassId = ?",[enrollment.ClassId])
    # checking if class exists
    entry = cur.fetchone()
    if(not entry):
        raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail= 'The Class Does Not Exist',
            )
    currentEnrollment, maxEnrollment, automaticEnrollmentFrozen = entry
    # checking if student exist
    cur = db.execute("Select * from Students where StudentId = ?",[enrollment.StudentId])
    entry = cur.fetchone()
    if(not entry):
        raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail= 'Student Does Not Exist',
            )
    # Checking if enrollment is possible
    if(automaticEnrollmentFrozen==1):
        raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail= 'Enrollment is closed',
            )

    # Checking if student is enrolled in a course
    cur = db.execute("Select * from Enrollments where ClassId = ? and  StudentId = ? and dropped = 0",[enrollment.ClassId, enrollment.StudentId])
    sameClasses = cur.fetchall()
    if(sameClasses):
        raise HTTPException(status_code=409, detail="You are already enrolled") #HTTP status code 409: "Conflict." 
    
    # Checking if Class is full then adding student to waitlist
    if(currentEnrollment >= maxEnrollment):

        # Checks if student is already on waitList
        cur = db.execute("Select * from WaitingLists where ClassId = ? and  StudentId = ?",[enrollment.ClassId, enrollment.StudentId])
        alreadyOnWaitlist = cur.fetchall()
        if(alreadyOnWaitlist):
            raise HTTPException(status_code=409, detail="You are already on waitlist") #HTTP status code 409, which stands for "Conflict." 

        # Checks that student is not on more than 3 waitlist (not checked)
        cur = db.execute("Select * from Waitinglists where StudentId = ?",[enrollment.StudentId])
        moreThanThree = cur.fetchall()
        if(len(moreThanThree)>3):
            raise HTTPException(status_code=409, detail="Class is full, already on three waitlists.") #HTTP status code 409, which stands for "Conflict." 
        
        # Adding to the waitlist if waitlist is not full
        cur = db.execute("Select * from Waitinglists where ClassId = ?",[enrollment.ClassId])
        entries = cur.fetchall()
        if(len(entries)>=15):
            raise HTTPException(status_code=403, detail="Waiting List if full for this class") # Forbidden
        waitListPosition = len(entries)+1
        e = dict(enrollment)
        try:
            cur = db.execute(
                """
                INSERT INTO WaitingLists(StudentID,ClassID,WaitingListPos,DateAdded)
                VALUES(?, ?, ? , datetime('now')) 
                """,
                [enrollment.StudentId,enrollment.ClassId,waitListPosition]
            )
            db.commit()
        except sqlite3.IntegrityError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"type": type(e).__name__, "msg": str(e)},
            )
        e["id"] = cur.lastrowid
        response.headers["Location"] = f"/WaitingLists/{e['id']}"
        message = f"Class is full you have been placed on waitlist position {waitListPosition}"
        # Checks if student was enrolled earlier
        raise HTTPException(status_code=400, detail=message)
    
    # Checks if student was enrolled earlier
    cur = db.execute("Select * from Enrollments where ClassId = ? and  StudentId = ?",[enrollment.ClassId, enrollment.StudentId])
    entry = cur.fetchone()
    if(entry):
        try:
            db.execute("""
                    UPDATE Enrollments SET dropped = 0 where ClassId = ? and StudentId = ?
                    """,
                    [enrollment.ClassId,enrollment.StudentId]) 
            db.execute("""
                    UPDATE Classes SET CurrentEnrollment = ? where ClassId = ? 
                    """,
                    [(currentEnrollment+1),enrollment.ClassId])
            db.commit()
        except sqlite3.IntegrityError as e:
            raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"type": type(e).__name__, "msg": str(e)},
        )
        return {"Success":"Enrolled"}
        
    else:
    # Register Students if class is not full
        e = dict(enrollment)
        try:
            cur = db.execute(
                """
                INSERT INTO enrollments(StudentId,ClassID,EnrollmentDate)
                VALUES(:StudentId, :ClassId, datetime('now')) 
                """,
                e,
            )
            # db.commit()
            # Updating currentEnrollment
            cur = db.execute("UPDATE Classes SET currentEnrollment = ? where ClassId = ?",[(currentEnrollment+1),enrollment.ClassId])
            db.commit()
        except sqlite3.IntegrityError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"type": type(e).__name__, "msg": str(e)},
            )
        e["id"] = cur.lastrowid
        response.headers["Location"] = f"/enrollments/{e['id']}"
        return {"Success":e}

# Delete enrollment of student
@app.delete("/students/{StudentId}/enrollments/{ClassId}",status_code=status.HTTP_200_OK)
def drop_enrollment(
    StudentId:int, ClassId:int , db: sqlite3.Connection = Depends(get_db)
):
    cur = db.execute("select CurrentEnrollment, MaxEnrollment, AutomaticEnrollmentFrozen from Classes where ClassId = ?",[ClassId])
    entries = cur.fetchone()
    # check if class exists
    if(not entries):
        raise HTTPException(status_code=404, detail="Class does not exist")
    currentEnrollment, maxEnrollment, automaticEnrollmentFrozen = entries

    # checks if student exist
    cur = db.execute("Select * from Students where StudentId = ?",[StudentId])
    entry = cur.fetchone()
    if(not entry):
        raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail= 'Student Does Not Exist',
            )
    
    # Checks if student was enrolled to the course
    cur = db.execute("Select * from Enrollments where ClassId = ? and  StudentId = ? and dropped = 0",[ClassId, StudentId])
    entries = cur.fetchone()
    if(not entries):
        raise HTTPException(status_code=404, detail="You are not enrolled in this course") #student enrollement not found
    # student_dropped = entries['dropped']
     
    # drops the course
    try:
        db.execute("""
                    UPDATE Enrollments SET dropped = 1 where ClassId = ? and StudentId = ?
                    """,
                    [ClassId,StudentId]) 
        db.execute("""
                    UPDATE Classes SET CurrentEnrollment = ? where ClassId = ? 
                    """,
                    [(currentEnrollment-1),ClassId])
        db.commit()
    except sqlite3.IntegrityError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"type": type(e).__name__, "msg": str(e)},
        )
    db.commit()
    cur = db.execute("Select * from WaitingLists where ClassId = ? ORDER BY WaitingListPos ASC",[ClassId])
    entry = cur.fetchone()
    if (not automaticEnrollmentFrozen and (currentEnrollment-1)<maxEnrollment and entry):

        # Enroll student who is on top of the waitlist
                # Checks if student was enrolled to that course earlier
        cur = db.execute("Select * from Enrollments where ClassId = ? and  StudentId = ?",[ClassId, entry['StudentId']])
        enrollment_entry = cur.fetchone()
        if(enrollment_entry):
            try:
                cur = db.execute("UPDATE Enrollments SET dropped = 0 where ClassId = ? and StudentId = ?",[ClassId, entry['StudentId']])
                db.execute("""
                        UPDATE Classes SET CurrentEnrollment = ? where ClassId = ? 
                        """,
                        [(currentEnrollment),ClassId])
                db.execute("""
                            DELETE FROM WaitingLists WHERE StudentId = ? and ClassId= ? 
                            """,
                            [entry['StudentId'],ClassId])
                
                db.commit()
            except sqlite3.IntegrityError as e:
                raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"type": type(e).__name__, "msg": str(e)},
            )
        else:
            try:
                cur = db.execute(
                """
                INSERT INTO enrollments(StudentId,ClassID,EnrollmentDate)
                VALUES(?, ?, datetime('now')) 
                """,
                [entry['StudentId'], ClassId],
            )
                db.execute("""
                            DELETE FROM WaitingLists WHERE StudentId = ? and ClassId= ? 
                            """,
                            [entry['StudentId'],ClassId])
                db.execute("""
                        UPDATE Classes SET CurrentEnrollment = ? where ClassId = ? 
                        """,
                        [(currentEnrollment),ClassId])
                db.commit()
            except sqlite3.IntegrityError as e:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"type": type(e).__name__, "msg": str(e)},
                )
        # update waitlist positions
        cur = db.execute("Select * from WaitingLists where ClassId = ? ORDER BY DateAdded ASC",[ClassId])
        entries = cur.fetchall()
        for entry in entries:
            try:
                db.execute("""
                            UPDATE WaitingLists SET WaitingListPos = ? where ClassId = ? and WaitListId = ?
                            """,
                            [(entry['WaitingListPos']-1),ClassId,entry['WaitListId']])
                db.commit()
            except sqlite3.IntegrityError as e:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"type": type(e).__name__, "msg": str(e)},
                )
        
        db.commit()
        return  {
                "Message": "Successfully dropped"
            }
    db.commit()
    return  {
                "Message": "Successfully dropped"
            }

# View Waiting List Position
@app.get("/students/{StudentId}/waiting-list/{ClassId}",status_code=status.HTTP_200_OK)
def retrieve_waitinglist_position(
    StudentId: int, ClassId: int, db: sqlite3.Connection = Depends(get_db)
):
    # checks if student exist
    cur = db.execute("Select * from Students where StudentId = ?",[StudentId])
    entry = cur.fetchone()
    if(not entry):
        raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail= 'Student Does Not Exist',
            )
    # checks if class exist
    cur = db.execute("Select * from classes where ClassId = ?",[ClassId])
    entry = cur.fetchone()
    if(not entry):
        raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail= 'Class Does Not Exist',
            )
    cur = db.execute("SELECT * FROM WaitingLists WHERE StudentId = ? and ClassId= ?", [StudentId,ClassId])
    waitingList = cur.fetchone()
    if not waitingList:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Position not found"
        )
    return  {
            "data": waitingList,
            "WaitingListPos":waitingList['WaitingListPos']
            }
    

# Remove from Waiting List
@app.delete("/students/{StudentId}/waiting-list/{ClassId}",status_code=status.HTTP_200_OK)
def delete_waitinglist(
    StudentId: int, ClassId: int, db: sqlite3.Connection = Depends(get_db)
):
    # checks if student exist
    cur = db.execute("Select * from Students where StudentId = ?",[StudentId])
    entry = cur.fetchone()
    if(not entry):
        raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail= 'Student Does Not Exist',
            )
    # checks if class exist
    cur = db.execute("Select * from classes where ClassId = ?",[ClassId])
    entry = cur.fetchone()
    if(not entry):
        raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail= 'Class Does Not Exist',
            )
    # Checks if entry exist in waitinglist
    cur = db.execute("SELECT * FROM WaitingLists WHERE StudentId = ? and ClassId= ?", [StudentId,ClassId])
    waitingList = cur.fetchone()
    if not waitingList:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not in Waitlist"
        )
     # updates waitlist positions
    try:
        cur = db.execute("Select * from WaitingLists where ClassId = ? and WaitListId > ?",[ClassId, waitingList['WaitListId']])
        entries = cur.fetchall()
        for entry in entries:
            db.execute("""
                        UPDATE WaitingLists SET WaitingListPos = ? where ClassId = ? and WaitListId = ?
                        """,
                        [(entry['WaitingListPos']-1),ClassId,entry['WaitListId']])
            db.commit()
        db.execute("DELETE FROM WaitingLists WHERE StudentId = ? and ClassId= ?", [StudentId,ClassId])
        db.commit()
    except sqlite3.IntegrityError as e:
        db.rollback()
        raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"type": type(e).__name__, "msg": str(e)},
            )
    db.commit()
    return  {
                "Message": "Successfully removed from the Waiting List"
            }

"""
API for Instructors Endpoints
"""

# View Current Enrollment for Their Classes
@app.get("/instructors/{InstructorId}/classes",status_code=status.HTTP_200_OK)
def retrieve_Instructors_Classes(
    InstructorId: int, db: sqlite3.Connection = Depends(get_db)
):
    # checks if instructor exist
    cur = db.execute("Select * from instructors where InstructorId = ?",[InstructorId])
    entry = cur.fetchone()
    if(not entry):
        raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail= 'Instructor Does Not Exist',
            )
    
    cur = db.execute("SELECT classname,currentenrollment FROM Classes WHERE InstructorId = ?", [InstructorId])
    instructorClasses = cur.fetchall()
    if not instructorClasses:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Instructor does not have any classes"
        )
    return  {
            "instructorClasses": instructorClasses
            }

# View the current waiting list for the course
@app.get("/classes/{ClassId}/wait-list",status_code=status.HTTP_200_OK)
def retrieve_Classes_WaitingList(
    ClassId: int, db: sqlite3.Connection = Depends(get_db)
):
    # checks if class exist
    cur = db.execute("Select * from classes where ClassId = ?",[ClassId])
    entry = cur.fetchone()
    if(not entry):
        raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail= 'Class Does Not Exist',
            )
    
    cur = db.execute("SELECT * FROM WaitingLists WHERE ClassId = ?", [ClassId])
    classesWaitingList = cur.fetchall()
    if not classesWaitingList:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Waiting List doest not exist for this class"
        )
    return  {
            "Total Waitlisted Students": len(classesWaitingList),
            "instructorClassesWaitingList": classesWaitingList
            }

# View Students Who Have Dropped the Class
@app.get("/instructors/{ClassId}/dropped-students",status_code=status.HTTP_200_OK)
def retrieve_instructors_dropped_students(
    ClassId:int, db: sqlite3.Connection = Depends(get_db)
):
    # checks if class exist
    cur = db.execute("Select * from classes where ClassId = ?",[ClassId])
    entry = cur.fetchone()
    if(not entry):
        raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail= 'Class Does Not Exist',
            )
    cur = db.execute("SELECT * FROM Students WHERE StudentId in (SELECT StudentId FROM Enrollments WHERE  ClassId = ? and Dropped = 1)", [ClassId])
    studentsWhoDropped = cur.fetchall()
    if not studentsWhoDropped:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No students have dropped this class"
        )
    return  {
            "Dropped Students": studentsWhoDropped
            }

# Drop students administratively
@app.delete("/instructors/{InstructorId}/drop-student/{StudentId}/{ClassId}")
def drop_students_administratively(
    InstructorId:int, StudentId:int, ClassId:int, db: sqlite3.Connection = Depends(get_db)
):
    # checks if instructor exist
    cur = db.execute("Select * from instructors where InstructorId = ?",[InstructorId])
    entry = cur.fetchone()
    if(not entry):
        raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail= 'Instructor Does Not Exist',
            )
    
    # checks if class exists
    cur = db.execute("select CurrentEnrollment, MaxEnrollment, AutomaticEnrollmentFrozen, InstructorId from Classes where ClassId = ?",[ClassId])

    entries = cur.fetchone()
    if(not entries):
        raise HTTPException(status_code=404, detail="Class does not exist")
    currentEnrollment, maxEnrollment, automaticEnrollmentFrozen, instructorId = entries

    # checks if InstructorId is valid
    if(InstructorId != instructorId):
        raise HTTPException(status_code=403, detail="You are not the instructor of this class") # Forbidden srtatus code

    # Checks if student was enrolled to the course
    cur = db.execute(
        """
        Select * from Enrollments where ClassId = ? and  StudentId = ? and dropped = 0
        """,
        [ClassId, StudentId])
    entries = cur.fetchone()
    if(not entries):
        raise HTTPException(status_code=404, detail="Student is not enrolled in this class") #Not Found 
     
    # drops the course
    try:
        db.execute("""
                    UPDATE Enrollments SET dropped = 1 where ClassId = ? and StudentId = ?
                    """,
                    [ClassId,StudentId]) 
        db.execute("""
                    UPDATE Classes SET CurrentEnrollment = ? where ClassId = ? 
                    """,
                    [(currentEnrollment-1),ClassId])
        db.commit()
    except sqlite3.IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"type": type(e).__name__, "msg": str(e)},
        )
    
    cur = db.execute("Select * from WaitingLists where ClassId = ? ORDER BY WaitingListPos ASC",[ClassId])
    entry = cur.fetchone()
    if (not automaticEnrollmentFrozen and (currentEnrollment-1)<maxEnrollment and entry):

        # Enroll student who is on top of the waitlist
                # Checks if student was enrolled to that course earlier
        cur = db.execute("Select * from Enrollments where ClassId = ? and  StudentId = ?",[ClassId, entry['StudentId']])
        enrollment_entry = cur.fetchone()
        if(enrollment_entry):
            try:
                cur = db.execute("UPDATE Enrollments SET dropped = 0 where ClassId = ? and StudentId = ?",[ClassId, entry['StudentId']])
                db.execute("""
                        UPDATE Classes SET CurrentEnrollment = ? where ClassId = ? 
                        """,
                        [(currentEnrollment),ClassId])
                db.execute("""
                            DELETE FROM WaitingLists WHERE StudentId = ? and ClassId= ? 
                            """,
                            [entry['StudentId'],ClassId])
                
                db.commit()
            except sqlite3.IntegrityError as e:
                raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"type": type(e).__name__, "msg": str(e)},
            )
        else: # adding him to the enrollments
            try:
                cur = db.execute(
                """
                INSERT INTO enrollments(StudentId,ClassID,EnrollmentDate)
                VALUES(?, ?, datetime('now')) 
                """,
                [entry['StudentId'], ClassId],
            )
                db.execute("""
                            DELETE FROM WaitingLists WHERE StudentId = ? and ClassId= ? 
                            """,
                            [entry['StudentId'],ClassId])
                db.execute("""
                        UPDATE Classes SET CurrentEnrollment = ? where ClassId = ? 
                        """,
                        [(currentEnrollment),ClassId])
                db.commit()
            except sqlite3.IntegrityError as e:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"type": type(e).__name__, "msg": str(e)},
                )
        # updating waitlist positions
        cur = db.execute("Select * from WaitingLists where ClassId = ? ORDER BY DateAdded ASC",[ClassId])
        entries = cur.fetchall()
        for entry in entries:
            try:
                db.execute("""
                            UPDATE WaitingLists SET WaitingListPos = ? where ClassId = ? and WaitListId = ?
                            """,
                            [(entry['WaitingListPos']-1),ClassId,entry['WaitListId']])
                db.commit()
            except sqlite3.IntegrityError as e:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"type": type(e).__name__, "msg": str(e)},
                )
        db.commit()
        return  {
                "Message": "Student Dropped Successfully"
            }
    
    db.commit()
    return  {
                "Message": "Student Dropped Successfully"
            }


#### API for Register Endpoints ####

# Add New Classes and Sections
@app.post("/classes/", status_code=status.HTTP_201_CREATED)
def create_class(
    class_: Class, response: Response, db: sqlite3.Connection = Depends(get_db)
):
    
    # checking if same class and section exist
    cur = db.execute("Select * from classes where ClassName = ? and SectionNumber = ?",[class_.ClassName, class_.SectionNumber])
    entry = cur.fetchone()
    newClassId = 0
    if(entry):
        raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail= 'Class Already Exist',
            )
    try:
        cur = db.execute(
            """
            INSERT INTO Classes(InstructorId,Department,CourseCode,SectionNumber,
            ClassName,CurrentEnrollment,MaxEnrollment,AutomaticEnrollmentFrozen)
            VALUES(?, ?, ? , ?, ?, 0, ?, ?) 
            """,
                [class_.InstructorId,class_.Department,class_.CourseCode,class_.SectionNumber,
                class_.ClassName,class_.MaxEnrollment,class_.AutomaticEnrollmentFrozen]
            )
        newClassId = cur.lastrowid
        db.commit()
    except sqlite3.IntegrityError as e:
        db.rollback()
        raise HTTPException(
        status_code=status.HTTP_40, 
        detail={"type": type(e).__name__, "msg": str(e)},
        )
    response.headers["Location"] = f"/classes/{newClassId}"
    return {'status':"Class created successfully"}

# Remove Existing Sections
@app.delete("/classes/{ClassId}",status_code=status.HTTP_200_OK)
def remove_section(
    ClassId:int , db: sqlite3.Connection = Depends(get_db)
):
    # checks if class exist
    cur = db.execute("Select * from classes where ClassId = ?",[ClassId])
    entry = cur.fetchone()
    if(not entry):
        raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail= 'Class Does Not Exist',
            )
    try:
        db.execute(
            """
            DELETE FROM Classes WHERE ClassId= ? 
            """,
            [ClassId])
        # Remove students from enrollments and waitlists
        db.execute(
            """
            DELETE FROM Enrollments WHERE ClassId= ? 
            """,
            [ClassId])
        db.execute(
            """
            DELETE FROM WaitingLists WHERE ClassId= ? 
            """,
            [ClassId])
        db.commit()
    except sqlite3.IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_40, 
            detail={"type": type(e).__name__, "msg": str(e)},
        )
    return {'status':"Class Deleted Successfully"}

# Change Instructor for a Section
@app.put("/classes/{ClassId}/instructor",status_code=status.HTTP_200_OK)
def change_instructor(
    ClassId:int, Instructor:UpdateInstructor , db: sqlite3.Connection = Depends(get_db)
):
    # checks if class exist
    cur = db.execute("Select * from classes where ClassId = ?",[ClassId])
    entry = cur.fetchone()
    if(not entry):
        raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail= 'Class Does Not Exist',
            )
    # checks if instructor exist
    cur = db.execute("Select * from instructors where InstructorId = ?",[Instructor.InstructorId])
    entry = cur.fetchone()
    if(not entry):
        raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail= 'Instructor Does Not Exist',
            )
    try:
        db.execute(
            """
            UPDATE Classes SET InstructorId = ? where ClassId = ?
            """,
            [Instructor.InstructorId,ClassId])
        db.commit()
    except sqlite3.IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_40, 
            detail={"type": type(e).__name__, "msg": str(e)},
        )
    return {'status':"Instructor Changed Successfully"}


# Freeze automatic enrollment from waiting lists
@app.put("/classes/{ClassId}/freeze-enrollment",status_code=status.HTTP_200_OK)
def freeze_enrollment(
    ClassId:int, db: sqlite3.Connection = Depends(get_db)
):
    # checks if class exist
    cur = db.execute("Select * from classes where ClassId = ?",[ClassId])
    entry = cur.fetchone()
    if(not entry):
        raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail= 'Class Does Not Exist',
            )
    if(entry['AutomaticEnrollmentFrozen'] == 1):
        raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail= 'Automatic Enrollment Frozen is already ON',
            ) 
    try:
        db.execute(
            """
            UPDATE Classes SET AutomaticEnrollmentFrozen = 1 where ClassId = ?
            """,
            [ClassId])
        db.commit()
    except sqlite3.IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_40, 
            detail={"type": type(e).__name__, "msg": str(e)},
        )
    return {'status':"Successfully turned on automatic enrollment frozen"}