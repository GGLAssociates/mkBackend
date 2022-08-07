from typing import Union
from fastapi import FastAPI, HTTPException, Depends, Request
from pydantic import BaseModel
import hashlib
from utils.utils import create_connection, create_table, insert_user, verbose_exception_message
from jose import jwt
import datetime 
from fastapi.responses import JSONResponse
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware
import os
from enum import Enum
import json
import pipeline.pipeline as pipeline

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

class UpdateUser(BaseModel):
    roleId : str

class CreateUser(BaseModel):
    username: str
    password: str
    roleId: int

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
        CREATE TABLE IF NOT EXISTS WorldTable (ID INTEGER PRIMARY KEY, WorldName varchar(255), ServerStatus INTEGER, IPAddress varchar(255), MachineName varchar(255));
        """
        create_table(conn, sql_create_worlds_table)
        
        # Close the connection
        conn.close()

def verify_token(req: Request):
    try:
        token = req.headers["token"]
        token = jwt.decode(token, SECRET, algorithms=['HS256'])
    except:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized, you have not logged in or have provided an invalid token"
        )
    role_id = token['roleId']
    # Check if the user has pemission to view the world list
    if role_id in set(item.value for item in RoleID):
        valid = True
    if not valid:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized"
        )
    return role_id
    
@app.get("/", tags=["Main"])
def read_root():
    return {"Hello": "World"}

""" Endpoint to create a new Minecraft world
    world_name: str 
"""

@app.get("/servers", tags=["World"])
async def servers(
    role_id: str = Depends(verify_token)):
    auth_users = [RoleID.ADMIN.value, RoleID.VISITOR.value]
    if role_id in auth_users:
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
            worlds.append({"id":row[0],"worldName": row[1], "ipAddress": row[3], "serverStatus": row[2]})
        return JSONResponse(status_code=200, content=json.dumps(worlds)) 
    else:
        return JSONResponse(status_code=401, content={"error": "You do not have permission to view this list"})

@app.post("/create_server", tags=["World"])
async def create_world(
    world: World, 
    role_id: bool = Depends(verify_token)):
    auth_users = [RoleID.ADMIN.value, RoleID.VISITOR.value]
    if role_id in auth_users:
        # Local database location
        database = Path('./sqlite/db/pythonsqlite.db')
        # Connect to the local SQLite database
        conn = create_connection(database)
        # Insert the new world into the Worlds table if it doesn't already exist and the user has permission to do so
        # data = pipeline.gcp_integrator(settings_file='./pipeline/settings.conf').create_instance()
        # ipAddress = data.ip
        # machineName = data.name
        ipAddress = 'joseph.fix.this'
        machineName = 'josephbot'
        try:
            cur = conn.cursor()
            # Insert the new world into the Worlds table with the ID of the next available ID, if an ID exists
            cur.execute("INSERT INTO WorldTable (WorldName, IPAddress, ServerStatus, MachineName) VALUES (?, ?, ?, ?)", (world.worldName, ipAddress, ServerStatus.ON.value, machineName))
            ID = cur.lastrowid
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
    
@app.delete("/world/{world_id}", tags=["World"])
async def delete_world(
    world_id: int, 
    role_id: bool = Depends(verify_token)):
    auth_users = [RoleID.ADMIN.value]
    if role_id in auth_users:
        # Local database location
        database = Path('./sqlite/db/pythonsqlite.db')
        # Connect to the local SQLite database
        conn = create_connection(database)
        # Create a cursor object
        cur = conn.cursor()
        # Get the machine name of the world to be deleted if it exists
        # machine_name = cur.execute("SELECT MachineName FROM WorldTable WHERE ID = ?", (world_id)).fetchone()[0]
        # Send a delete request to the pipeline to delete the world
        # pipeline.gcp_integrator(settings_file='./pipeline/settings.conf').delete_instance(machine_name)
        # Delete the world from the gcp bucket
        # pipeline.gcp_integrator(settings_file='./pipeline/settings.conf').delete_file('worlds/{machine_name}/world.zip'.format(machine_name=machine_name))
        # Delete the world from the Worlds table if it exists and the user has permission to do so
        cur.execute("DELETE FROM WorldTable WHERE ID = ?", (world_id,))
        conn.commit()
        return JSONResponse(status_code=200, content={"message": "World deleted", "success":True})
    else:
        return JSONResponse(status_code=401, content={"message": "You do not have permission to delete this world"})

""" Endpoint to stop a Minecraft world
    world name: str 
"""

@app.put("/stop_world/{world_id}", tags=["World"])
async def stop_world(
    world_id: int, 
    role_id: bool = Depends(verify_token)):
    auth_users = [RoleID.ADMIN.value]
    if role_id in auth_users:
        # Local database location
        database = Path('./sqlite/db/pythonsqlite.db')
        # Connect to the local SQLite database
        conn = create_connection(database)
        # Create a cursor object
        cur = conn.cursor()
        # Get the machine name of the world to be stopped if it exists
        # machine_name = cur.execute("SELECT MachineName FROM WorldTable WHERE ID = ?", (world_id)).fetchone()[0]
        # Send a stop request to the pipeline to stop the world
        # data = pipeline.gcp_integrator(settings_file='./pipeline/settings.conf').delete_instance(machine_name)
        # Stop the world in the Worlds table if it exists and the user has permission to do so
        cur.execute("UPDATE WorldTable SET ServerStatus = ? WHERE ID = ?", (ServerStatus.OFF.value, world_id))
        conn.commit()
        return JSONResponse(status_code=200, content={"message": "World stopped", 'success': True})
    else:
        return JSONResponse(status_code=401, content={"message": "You do not have permission to stop this world"})

""" Endpoint to load a Minecraft world from a Google storage bucket
    world_name: str 
"""
@app.put("/start_world/{world_id}", tags=["World"])
async def load_world(
    world_id: int, 
    role_id: bool = Depends(verify_token)):
    auth_users = [RoleID.ADMIN.value]
    if role_id in auth_users:
        # Local database location
        database = Path('./sqlite/db/pythonsqlite.db')
        # Connect to the local SQLite database
        conn = create_connection(database)
        # Create a cursor object
        cur = conn.cursor()
        # Get the machine associated with the world, this is the also the world_name to be loaded
        # world_name = cur.execute("SELECT MachineName FROM WorldTable WHERE ID = ?", (world_id)).fetchone()[0]
        # Send a load request to the pipeline to load the world
        # data = pipeline.gcp_integrator(settings_file='./pipeline/settings.conf').load_instance(world_name)
        cur.execute("UPDATE WorldTable SET ServerStatus = ? WHERE ID = ?", (ServerStatus.ON.value, world_id))
        conn.commit()
        return JSONResponse(status_code=200, content={"message": "World loaded", "success": True})
    else:
        return JSONResponse(status_code=401, content={"message": "You do not have permission to load this world"})


""" Login to the web server querying the database for an existing user and password.
    Return a response Cookie with a JWT token if the user is found.
    username: str
    password: str

"""

@app.post ("/login", tags=["Website"])
async def login(user: User):
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
async def register(
    request: CreateUser,
    role_id: bool = Depends(verify_token)):
    auth_users = [RoleID.ADMIN.value]
    if role_id in auth_users:
        # Load the database
        database = Path('./sqlite/db/pythonsqlite.db')
        conn = create_connection(database)
        # Check if the user is an admin
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
                return {"message": "User created", "success": True}
        except Exception as e:
            verbose_exception_message()
            return {"message": "Exception occured, Error: " + repr(e)}
    else:
        JSONResponse(status_code=401, content={"message": "You do not have permission to create a user"})

@app.get("/users", tags=["Website"])
async def get_users(role_id: bool = Depends(verify_token)):
    auth_users = [RoleID.ADMIN.value]
    if role_id in auth_users:
        # Load the database
        database = Path('./sqlite/db/pythonsqlite.db')
        conn = create_connection(database)
        # Check if the user is an admin
        try:
            cur = conn.cursor()
            # Check if the username already exists
            cur.execute("SELECT * FROM UserTable")
            rows = cur.fetchall()
            users = []
            for row in rows:
                users.append({"id": row[0], "username":row[1], "roleId": row[3]})
            return users
        except Exception as e:
            verbose_exception_message()
            return {"message": "Exception occured, Error: " + repr(e)}
    else:
        JSONResponse(status_code=401, content={"message": "You do not have permission to view users"})

""" 
Update the role of a user in the database, via a put request.
"""
@app.put("/user/{user_id}", tags=["Website"])
async def update_user(user_id: int, request: UpdateUser, role_id: bool = Depends(verify_token)):
    auth_users = [RoleID.ADMIN.value]
    if role_id in auth_users:
        # Load the database
        database = Path('./sqlite/db/pythonsqlite.db')
        conn = create_connection(database)
        # Check if the user is an admin
        try:
            cur = conn.cursor()
            # Check if the username already exists
            cur.execute("SELECT * FROM UserTable WHERE ID = ?", (user_id,))
            if cur.fetchone():
                # Update the user in the database
                cur.execute("UPDATE UserTable SET RoleID = ? WHERE ID = ?", (request.roleId, user_id))
                conn.commit()
                return {"message": "User updated", "success": True}
            else:
                return {"message": "User not found"}
        except Exception as e:
            verbose_exception_message()
            return {"message": "Exception occured, Error: " + repr(e)}
    else:
        JSONResponse(status_code=401, content={"message": "You do not have permission to update users"})

"""
Delete a user from the database, via a delete request.
"""  
@app.delete("/user/{user_id}", tags=["Website"])
async def delete_user(user_id: int, role_id: bool = Depends(verify_token)):
    auth_users = [RoleID.ADMIN.value]
    if role_id in auth_users:
        # Load the database
        database = Path('./sqlite/db/pythonsqlite.db')
        conn = create_connection(database)
        # Check if the user is an admin
        try:
            cur = conn.cursor()
            # Check if the username exists
            cur.execute("SELECT * FROM UserTable WHERE ID = ?", (user_id,))
            if cur.fetchone():
                # Delete the user from the database
                cur.execute("DELETE FROM UserTable WHERE ID = ?", (user_id,))
                conn.commit()
                return {"message": "User deleted", "success": True}
            else:
                return {"message": "User not found"}
        except Exception as e:
            verbose_exception_message()
            return {"message": "Exception occured, Error: " + repr(e)}
    else:
        JSONResponse(status_code=401, content={"message": "You do not have permission to delete users"})
