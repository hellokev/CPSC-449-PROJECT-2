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
        check_username = db.execute("SELECT * FROM USER WHERE username=:username", reg_user)
        
        # if the username exists, then return 409.    
        if check_username:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username taken."
            )
        
        hash_pw = hash_password(reg_user["password"])

        # Inserting registered user to database.
        db.execute("""
            INSERT INTO User (username, password)
            VALUES (:username, :hash_pw)
        """, {"username": reg_user["username"], "hash_pw": hash_pw})

        for role in reg_user["roles"]:
             db.execute("""
                INSERT INTO Roles (r_username, role)
                VALUES (:username, :role)
                        """, {"username": reg_user["username"], "role": ["role"]})
        claims = generate_claims(reg_user["username"], reg_user["roles"])

        db.commit()

        return claims
