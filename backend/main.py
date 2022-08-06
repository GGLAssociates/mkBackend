from typing import Union
from fastapi import FastAPI, Form
from pydantic import BaseModel
import sqlite3
import hashlib
from utils.utils import create_connection, create_table, insert_user
from jose import jwt
import datetime 
from fastapi.responses import JSONResponse
from pathlib import Path
import sys 
import traceback
from fastapi.middleware.cors import CORSMiddleware
import os
from enum import Enum

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
    

class CreateWorld(BaseModel):
    worldName: str
    ipAddress: str
    token: str
    

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
        CREATE TABLE IF NOT EXISTS WorldTable (ID INTEGER PRIMARY KEY, WorldName varchar(255));
        """
        create_table(conn, sql_create_worlds_table)
        
        # Close the connection
        conn.close()
        
@app.get("/", tags=["Main"])
def read_root():
    return {"Hello": "World"}

""" Endpoint to create a new Minecraft world
    world_name: str 
"""

@app.post("/create_world", tags=["World"])
def create_world(request: CreateWorld):
    # Local database location
    database = Path('./sqlite/db/pythonsqlite.db')
    # Connect to the local SQLite database
    conn = create_connection(database)
    # Insert the new world into the Worlds table if it doesn't already exist and the user has permission to do so
    if request.token != None:
        # Check if the user is an admin
        token = jwt.decode(request.token, SECRET, algorithms=['HS256'])
        role_id = token['roleId']
        exp = token['exp']
        if exp < int(datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")):
            return {"message": "Token expired"}
        if role_id == RoleID.ADMIN.value:
            try:
                # Check if the world already exists
                cur = conn.cursor()
                cur.execute("SELECT WorldName FROM WorldTable WHERE WorldName = ?", (request.worldName,))
                if cur.fetchone():
                    return {"message": "World exists with this name, please choose another name"}
                else:
                    # Insert the new world into the Worlds table with the ID of the next available ID, if an ID exists
                    cur.execute("SELECT ID FROM WorldTable ORDER BY ID DESC LIMIT 1")
                    if cur.fetchone():
                        ID = cur.fetchone()[0] + 1
                        cur.execute("INSERT INTO WorldTable (ID, WorldName, IPAddress, ServerStatus) VALUES (?, ?, ?, ?)", (ID, request.worldName, request.ipAddress, ServerStatus.PENDING.value))
                    else:
                        ID = 1
                        cur.execute("INSERT INTO WorldTable (ID, WorldName, IPAddress, ServerStatus) VALUES (?, ?, ?, ?)", (ID, request.worldName, request.ipAddress, ServerStatus.PENDING.value))
                    conn.commit()
                    # Return the new world's ID, name
                    return {"id": ID, "name": request.worldName, "ipAddress": request.ipAddress, "serverStatus": ServerStatus.PENDING.value}
            except Exception as e:
                # Get current system exception
                ex_type, ex_value, ex_traceback = sys.exc_info()

                # Extract unformatter stack traces as tuples
                trace_back = traceback.extract_tb(ex_traceback)

                # Format stacktrace
                stack_trace = list()

                for trace in trace_back:
                    stack_trace.append("File : %s , Line : %d, Func.Name : %s, Message : %s" % (trace[0], trace[1], trace[2], trace[3]))

                print("Exception type : %s " % ex_type.__name__)
                print("Exception message : %s" %ex_value)
                print("Stack trace : %s" %stack_trace)
                return {"message": "Exception occured, Error: " + repr(e)}

""" Endpoint to delete a Minecraft world
    world name: str 
"""
    
@app.post("/delete_world/{world_name}", tags=["World"])
def delete_world(world_name: str):
    
    return {"world_name": world_name}

""" Endpoint to restart a Minecraft world
    world_name: str 
"""

@app.post("/restart_world/{world_name}", tags=["World"])
def restart_world(world_name: str):
    return {"world_name": world_name}

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
        # Get current system exception
        ex_type, ex_value, ex_traceback = sys.exc_info()

        # Extract unformatter stack traces as tuples
        trace_back = traceback.extract_tb(ex_traceback)

        # Format stacktrace
        stack_trace = list()

        for trace in trace_back:
            stack_trace.append("File : %s , Line : %d, Func.Name : %s, Message : %s" % (trace[0], trace[1], trace[2], trace[3]))

        print("Exception type : %s " % ex_type.__name__)
        print("Exception message : %s" %ex_value)
        print("Stack trace : %s" %stack_trace)
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
                # Get current system exception
                ex_type, ex_value, ex_traceback = sys.exc_info()

                # Extract unformatter stack traces as tuples
                trace_back = traceback.extract_tb(ex_traceback)

                # Format stacktrace
                stack_trace = list()

                for trace in trace_back:
                    stack_trace.append("File : %s , Line : %d, Func.Name : %s, Message : %s" % (trace[0], trace[1], trace[2], trace[3]))

                print("Exception type : %s " % ex_type.__name__)
                print("Exception message : %s" %ex_value)
                print("Stack trace : %s" %stack_trace)
                return {"message": "Exception occured, Error: " + repr(e)}

        