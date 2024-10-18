from pydantic import BaseModel, constr

class UserRegistration(BaseModel):

    email : str
    username: constr(to_lower=True) # type: ignore
    password : str

    # NOTE: This is case-sensitive
    display_name : str