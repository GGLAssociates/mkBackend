import jwt

class verify():
    def __init__(self, secret_val):
        self.secret = secret_val

    def validate(self, jwt, roles):
        jwt.decode(jwt, self.secret, algorithms=["HS256"])
        
