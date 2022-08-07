import ipaddress
from typing import Union
from fastapi import FastAPI, HTTPException, Depends, Request
from pydantic import BaseModel
import sqlite3
import hashlib
from utils.utils import create_connection, create_table, insert_user, verbose_exception_message
from jose import jwt
import datetime 
from fastapi.responses import JSONResponse
from pathlib import Path
import sys 
import traceback
from fastapi.middleware.cors import CORSMiddleware
import os
from enum import Enum
import json
import jwt


SECRET = os.environ.get('SECRET')

app = FastAPI(title="Minecraft Server Backend Endpoints",
    description="Endpoints for the GGLAssociates MK Minecraft Server Backend API",
    version="0.0.1",
    contact={
        "name": "GGLAssociates",
        "url": "https://gglassociates.com",
        "email": "GGLAssociates.Contact@gmail.com",
    },
    license_info={
        "name": "Apache 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
    },
)

class ServerStatus(Enum):
    OFF = 1
    PENDING = 2
    ON = 3
    PENDING_DOWN = 4
    ERROR = 5
    
class RoleID(Enum):
    ADMIN = 1
    VISITOR = 2
    

class World(BaseModel):
    worldName: str
class User(BaseModel):
    username: str
    password: str

class CreateUser(BaseModel):
    username: str
    password: str
    roleId: int
    token: str

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def validate(jwt, role):
    jwt.decode(jwt, SECRET, algorithms=["HS256"])

@app.on_event("startup")
def startup_event():
    """ 
    On startup, create the SQLite database file if it doesn't exist.
    """
    # Default database location
    database = Path('./sqlite/db/pythonsqlite.db')
    if database.is_file():
        print("Database exists")
    else:
        print("Database does not exist, generating default roles and users") 
        # Connect to the local SQLite database
        conn = create_connection(database)
        
        # Create Users Table
        sql_create_users_table = """ 
        CREATE TABLE IF NOT EXISTS UserTable (ID INTEGER PRIMARY KEY, Username varchar(255), Password varchar(255), RoleID INTEGER);
        """
        user = """
        INSERT INTO UserTable (ID, Username, Password, RoleID) VALUES (1, "admin", "ac9689e2272427085e35b9d3e3e8bed88cb3434828b43b86fc0596cad4c6e270.1234", 1);
        """
        create_table(conn, sql_create_users_table)
        insert_user(conn, user)
        
        # Create Roles Table
        sql_create_roles_table = """ 
        CREATE TABLE IF NOT EXISTS RoleTable (RoleID INTEGER, RoleName varchar(255));
        """
        admin = """
        INSERT INTO RoleTable (RoleID, RoleName) VALUES (1, "admin");
        """
        visitor = """
        INSERT INTO RoleTable (RoleID, RoleName) VALUES (2, "vistor");
        """
        
        create_table(conn, sql_create_roles_table)
        insert_user(conn, admin)
        insert_user(conn, visitor)

        # Create Worlds table
        
        sql_create_worlds_table = """ 
        CREATE TABLE IF NOT EXISTS WorldTable (ID INTEGER PRIMARY KEY, WorldName varchar(255), ServerStatus INTEGER);
        """
        create_table(conn, sql_create_worlds_table)
        
        # Close the connection
        conn.close()

def verify_token_admin(req: Request):
    token = req.headers["token"]
    token = jwt.decode(token, SECRET, algorithms=['HS256'])
    role_id = token['roleId']
    exp = token['exp']
    if exp < int(datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")):
        return {"message": "Token expired"}
    
    # Check if the user has pemission to view the world list
    if role_id == RoleID.ADMIN.value:
        valid = True
    if not valid:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized"
        )
    return True

def verify_token(req: Request):
    token = req.headers["token"]
    token = jwt.decode(token, SECRET, algorithms=['HS256'])
    role_id = token['roleId']
    exp = token['exp']
    if exp < int(datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")):
        return {"message": "Token expired"}
    
    # Check if the user has pemission to view the world list
    if role_id in set(item.value for item in RoleID):
        valid = True
    if not valid:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized"
        )
    return req, True
    
@app.get("/", tags=["Main"])
def read_root():
    return {"Hello": "World"}

""" Endpoint to create a new Minecraft world
    world_name: str 
"""

@app.get("/servers", tags=["World"])
def servers(authorized = Depends(verify_token)):
    if authorized:
        """
        List all worlds in the database
        """
        database = Path('./sqlite/db/pythonsqlite.db')
        # Connect to the local SQLite database
        conn = create_connection(database)
        # Create a cursor object
        cur = conn.cursor()
        # Get all worlds from the database
        cur.execute("SELECT * FROM WorldTable")
        rows = cur.fetchall()
        worlds = []
        for row in rows:
            worlds.append({"ID":row[0],"worldName": row[1], "ipAddress": row[2], "serverStatus": row[3]})
        return JSONResponse(status_code=200, content=json.dumps(worlds)) 
    else:
        return JSONResponse(status_code=401, content={"error": "You do not have permission to view this list"})

@app.post("/create_server", tags=["World"])
def create_world(authorised: bool = Depends(verify_token)):
    
    # Local database location
    database = Path('./sqlite/db/pythonsqlite.db')
    # Connect to the local SQLite database
    conn = create_connection(database)
    # Insert the new world into the Worlds table if it doesn't already exist and the user has permission to do so
    ipAddress = '1.1.1.1'
    if authorised:
        try:
            cur = conn.cursor()
            # Insert the new world into the Worlds table with the ID of the next available ID, if an ID exists
            cur.execute("SELECT ID FROM WorldTable ORDER BY ID DESC LIMIT 1")
            if cur.fetchone():
                ID = cur.fetchone()[0] + 1
                cur.execute("INSERT INTO WorldTable (ID, WorldName, IPAddress, ServerStatus) VALUES (?, ?, ?, ?)", (ID, world.worldName, ipAddress, ServerStatus.PENDING.value))
            else:
                ID = 1
                cur.execute("INSERT INTO WorldTable (ID, WorldName, IPAddress, ServerStatus) VALUES (?, ?, ?, ?)", (ID, world.worldName, ipAddress, ServerStatus.PENDING.value))
            conn.commit()
            # Return the new world's ID, name
            return {"id": ID, "name": world.worldName, "ipAddress": ipAddress, "serverStatus": ServerStatus.PENDING.value}
        except Exception as e:
            verbose_exception_message()
            return {"message": "Exception occured, Error: " + repr(e)}
    else:
        return JSONResponse(status_code=401, content={"message": "You do not have permission to create a world"})

""" Endpoint to delete a Minecraft world
    world name: str 
"""
    
@app.post("/delete_world", tags=["World"])
def delete_world(request: World):
    # Local database location
    database = Path('./sqlite/db/pythonsqlite.db')
    # Connect to the local SQLite database
    conn = create_connection(database)
    # Delete the world from the Worlds table if it exists and the user has permission to do so
    # Check if the user is an admin
    token = jwt.decode(request.token, SECRET, algorithms=['HS256'])
    role_id = token['roleId']
    exp = token['exp']
    if exp < int(datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")):
        return {"message": "Token expired"}
    if role_id == RoleID.ADMIN.value:
        try:
            # Check if the world exists
            cur = conn.cursor()
            cur.execute("SELECT WorldName FROM WorldTable WHERE WorldName = ?", (request.worldName,))
            if cur.fetchone():
                # Delete the world from the Worlds table
                cur.execute("DELETE FROM WorldTable WHERE WorldName = ?", (request.worldName,))
                conn.commit()
                return {"message": "World deleted"}
            else:
                return {"message": "World does not exist"}
        except Exception as e:
            verbose_exception_message()
            return {"message": "Exception occured, Error: " + repr(e)}
    else:
        return JSONResponse(status_code=401, content={"message": "You do not have permission to delete a world"})
        
""" Endpoint to restart a Minecraft world
    world_name: str 
"""

@app.post("/restart_world", tags=["World"])
def restart_world(request: World):
    # Local database location
    database = Path('./sqlite/db/pythonsqlite.db')
    # Connect to the local SQLite database
    conn = create_connection(database)
    # Restart the world if it exists and the user has permission to do so
    # Check if the user is an admin
    token = jwt.decode(request.token, SECRET, algorithms=['HS256'])
    role_id = token['roleId']
    exp = token['exp']
    if exp < int(datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")):
        return {"message": "Token expired"}
    if role_id == RoleID.ADMIN.value:
        try:
            # Check if the world exists
            cur = conn.cursor()
            cur.execute("SELECT WorldName FROM WorldTable WHERE WorldName = ?", (request.worldName,))
            if cur.fetchone():
                # Restart the world
                cur.execute("UPDATE WorldTable SET ServerStatus = ? WHERE WorldName = ?", (ServerStatus.PENDING_DOWN.value, request.worldName))
                conn.commit()
                return {"message": "World restarted"}
            else:
                return {"message": "World does not exist"}
        except Exception as e:
            verbose_exception_message()
            return {"message": "Exception occured, Error: " + repr(e)}
    else:
        JSONResponse(status_code=401, content={"message": "You do not have permission to restart a world"})

""" Endpoint to stop a Minecraft world
    world name: str 
"""

@app.post("/stop_world/{world_name}", tags=["World"])
def stop_world(world_name: str):
    return {"world_name": world_name}

""" Endpoint to load a Minecraft world from a Google storage bucket
    world_name: str 
"""
@app.post("/load_world/{world_name}", tags=["World"])
def load_world(world_name: str):

    return {"world_name": world_name}
""" Login to the web server querying the database for an existing user and password.
    Return a response Cookie with a JWT token if the user is found.
    username: str
    password: str

"""

"""
Login to the Minecraft webserver.
"""
@app.post ("/login", tags=["Website"])
def login(user: User):
    # Query the database for the username and password
    # UserTable:
    # ID, Username, Password, RoleID
    
    # Load the database
    database = Path('./sqlite/db/pythonsqlite.db')
    conn = create_connection(database)
    
    # Connect to the database
    cur = conn.cursor()
    try:
        stored_password = cur.execute("SELECT Password FROM UserTable WHERE Username = ?", (user.username,)).fetchone()[0]
    except:
        return {"message": "Username not found"}
    try:
        # Stored password
        salt = stored_password.split(".")[1]
        role_id = cur.execute("SELECT RoleID FROM UserTable WHERE Username = ?", (user.username,)).fetchone()[0]
        # Convert plaintext + salt password to hash
        password = hashlib.sha256((user.password+salt).encode()).hexdigest()
        if stored_password.split('.')[0] == password:
            exp_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=3600)
            exp_time = int(exp_time.strftime("%Y%m%d%H%M%S"))
            # exp_time = exp_time.isoformat()
            # Create JWT using python-jose with username, role, expiry time
            token = jwt.encode({'username': user.username, 'roleId': role_id, 'exp': exp_time}, SECRET, algorithm='HS256')
            # Send JWT to user as a cookie and a success message
            content = {"token": token}
            response = JSONResponse(content=content, status_code=200)
            return response
        else:
            return {"message": "Password incorrect"}
    except Exception as e:
        verbose_exception_message()
        return {"message": "Password incorrect, Error: " + repr(e)}
"""
Create a new user in the database.
"""
@app.post ("/register", tags=["Website"])
def register(request: CreateUser):
    # Load the database
    database = Path('./sqlite/db/pythonsqlite.db')
    conn = create_connection(database)
    if request.token != None:
        # Check if the user is an admin
        token = jwt.decode(request.token, SECRET, algorithms=['HS256'])
        role_id = token['roleId']
        exp = token['exp']
        if exp < int(datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")):
            return {"message": "User is not an admin"}
        if role_id == RoleID.ADMIN.value:
            try:
                cur = conn.cursor()
                # Check if the username already exists
                cur.execute("SELECT Username FROM UserTable WHERE Username = ?", (request.username,))
                if cur.fetchone():
                    return {"message": "Username already exists"}
                else:
                    # Create a salt and hash the password
                    salt = os.urandom(16)
                    password = hashlib.sha256((request.password+str(salt)).encode()).hexdigest()
                    # Insert the new user into the database
                    cur.execute("INSERT INTO UserTable (Username, Password, RoleID) VALUES (?, ?, ?)", (request.username, password+"."+str(salt), request.roleId))
                    conn.commit()
                    return {"message": "User created"}
            except Exception as e:
                verbose_exception_message()
                return {"message": "Exception occured, Error: " + repr(e)}

        