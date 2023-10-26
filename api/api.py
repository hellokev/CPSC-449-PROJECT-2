from collections import OrderedDict
from typing import List
from hash import *
from mkclaims import *

import contextlib
import logging.config
import sqlite3
import datetime
import random

from fastapi import FastAPI, Depends, Request, HTTPException, status
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
