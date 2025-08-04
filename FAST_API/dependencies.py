from fastapi import Request, HTTPException, status

def login_required(request: Request):
    """
    Dependency function to ensure a user is logged in.
    If not logged in, raises an HTTPException to redirect to the login page.
    """
    user = request.session.get("user_name")
    if not user:
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/auth/login"},
        )
    return user
