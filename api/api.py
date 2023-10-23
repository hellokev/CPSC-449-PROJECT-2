from collections import OrderedDict
from typing import List
from hash import *
from mkclaims import *

import contextlib
import logging.config
import sqlite3
import datetime

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
    logging_config: str

def get_db():
    with contextlib.closing(sqlite3.connect(settings.database)) as db:
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
def register_user(register: Register, request: Request, db: sqlite3.Connection = Depends(get_db)):
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
        """, (reg_user['username'], reg_user['password'])) #Corrected the query

        for role in reg_user["roles"]:
             db.execute("""
                INSERT INTO Roles (r_username, role)
                VALUES (?,?)
                        """, (reg_user["username"], role)) # will create Separate entries for different roles of Same username
        claims = generate_claims(reg_user["username"], None, reg_user["roles"])

        db.commit()

        return claims

# Task 2: Logging in a student
# Example: POST http://localhost:5000/login
# STATUS: INCOMPLETE
@app.post("/login")
def login_user(login: Login, request: Request, db: sqlite3.Connection = Depends(get_db)):
    user = dict(login)
    
    fetch_user = ("SELECT * FROM USER WHERE username=:username", user).fetchall()[0]
    if fetch_user.fetchone():             # Checks for correct login.
        raise HTTPException(
            status_code=status.HTTP_400_CONFLICT,
            detail="Invalid login."
        )