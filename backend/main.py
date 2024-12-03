from fastapi import FastAPI, Depends, HTTPException
from jose import JWTError
from datetime import datetime
from typing import Optional
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordBearer
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Notification, User
from pydantic import BaseModel
from fastapi import FastAPI, Request, Form, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from auth import verify_password, create_access_token, hash_password, decode_access_token
from models import User, Climb, UserInterest, FeedItem, Area, UserAssociation
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

app = FastAPI()


templates = Jinja2Templates(directory="templates")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """
    Retrieves the current user from the request by decoding the access token.
    This function will return the user object if the token is valid, otherwise None.
    """
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Decode the token (ensure your token decoding function is correct)
    token = token.replace("Bearer ", "")
    try:
        payload = decode_access_token(token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Get user info from the token's payload (this assumes 'sub' is the email)
    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    # Fetch the user from the database using the email
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

class NotificationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        db: Session = next(get_db())

        # Try to get the current user from the request
        current_user = None
        try:
            current_user = get_current_user(request, db=db)
        except HTTPException:
            current_user = None  # If no user is found, set it to None (i.e., user not authenticated)

        # Add the current user to the request state
        request.state.current_user = current_user

        # Handle unread notifications count for the current user
        unread_notifications_count = 0
        if current_user:
            unread_notifications_count = db.query(Notification).filter(
                Notification.user_id == current_user.id, Notification.read == False
            ).count()

        # Add unread notifications count to request state
        request.state.unread_notifications_count = unread_notifications_count

        # Proceed with the request
        response = await call_next(request)
        return response

app.add_middleware(NotificationMiddleware)

# Dependency to get the database session



def protect_route(request: Request, db: Session = Depends(get_db)):
    # Get the token from cookies
    token = request.cookies.get("access_token")
    if not token:
        return None


    # Decode the token
    token = token.replace("Bearer ", "")
    payload = decode_access_token(token)
    if not payload:
        return None
    # Get the current user
    email = payload.get("sub")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return None

    return user


@app.get("/login", response_class=HTMLResponse)
def show_login(request: Request, message: str | None = None):
    return templates.TemplateResponse("login.html", {"request": request, "message": message})


class RegisterUser(BaseModel):
    name: str
    email: str
    password: str

@app.post("/register")
def register_user(user: RegisterUser, db: Session = Depends(get_db)):
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Hash the password and save the user
    hashed_password = hash_password(user.password)
    new_user = User(name=user.name, email=user.email, password_hash=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "User registered successfully", "user_id": new_user.id}

class LoginUser(BaseModel):
    email: str
    password: str

@app.post("/login")
def login_user(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    # Find user in database
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        # Return the login page with an error
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid email or password"}
        )
    # Generate JWT token
    access_token = create_access_token(data={"sub": user.email})
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True)
    return response


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db), message: str | None = None):
    current_user = protect_route(request, db)
    if not current_user:
        return RedirectResponse(url="/login")

    following = [a.friend for a in current_user.following]
    followers = [a.user for a in current_user.followers]

    following_ids = [friend.id for friend in following]
    relevant_user_ids = [current_user.id] + following_ids

    feed_items = db.query(FeedItem).filter(
        FeedItem.user_id.in_(relevant_user_ids)
    ).order_by(FeedItem.timestamp.desc()).limit(5)

    climbs_of_interest = [interest.climb for interest in current_user.interests]


    user_climbs = db.query(Climb).join(UserInterest).filter(UserInterest.user_id == current_user.id).all()

    shared_interests = {}
    for climb in user_climbs:
        friends_with_interest = (
            db.query(User)
            .join(UserInterest)
           .filter(UserInterest.climb_id == climb.id, User.id.in_([friend.id for friend in following]))
            .all()
        )
        shared_interests[climb] = friends_with_interest

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "current_user": current_user,
            "feed_items": feed_items,
            "following": following,
            "followers": followers,
            "climbs_of_interest": climbs_of_interest,
            "shared_interests" : shared_interests,
            "message": message,
        }
    )
 

@app.post("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(key="access_token")
    return response



@app.get("/users", response_class=HTMLResponse)
def list_users(request: Request, db: Session = Depends(get_db), message: str | None = None):
    # Use protect_route to get the authenticated user
    current_user = protect_route(request, db)
    if not current_user:
        return RedirectResponse(url="/login")

    # Fetch all users except the authenticated user and their friends
    friends_ids = [friend.friend_id for friend in current_user.following]
    users = db.query(User).filter(User.id.notin_([current_user.id] + friends_ids)).all()

    return templates.TemplateResponse("users.html", {
        "request": request,
        "users": users,
        "current_user": current_user ,
        "message": message
    })




@app.post("/users/{id}/friends")
def add_friend_users(
    id: int,
    friend_id: int = Form(...),
    db: Session = Depends(get_db),
    request: Request = None
):
    current_user = protect_route(request, db)
    if not current_user:
        return RedirectResponse(url="/login")

    # Ensure the authenticated user is adding friends to their own account
    if current_user.id != id:
        raise HTTPException(status_code=403, detail="You cannot add follows for another user.")

    # Ensure the friend exists
    friend = db.query(User).filter(User.id == friend_id).first()
    if not friend:
        raise HTTPException(status_code=404, detail="User not found")

    # Ensure a user cannot follow themselves
    if current_user.id == friend_id:
        raise HTTPException(status_code=400, detail="You cannot follow yourself.")

    # Check if they're already following this user
    if db.query(UserAssociation).filter(
        UserAssociation.user_id == current_user.id,
        UserAssociation.friend_id == friend_id
    ).first():
        raise HTTPException(status_code=400, detail="You are already following this user.")

    # Add the follow relationship using the UserAssociation model
    new_follow = UserAssociation(
        user_id=current_user.id,
        friend_id=friend_id,
        followed_at=datetime.utcnow()  
    )
    db.add(new_follow)

    notification = Notification(
        user_id=friend_id,
        source_user_id=current_user.id,
        message=f"{current_user.name} started following you.",
        read=False,
        notification_type="follow"
    )
    db.add(notification)
    db.commit()

    feed_item = FeedItem(
        user_id=current_user.id,
        action="followed",
        details=f"followed {friend.name}"
    )
    db.add(feed_item)
    db.commit()

    return RedirectResponse(url=f"/users?message=Successfully added {friend.name} as a friend.", status_code=302)


@app.get("/climbs", response_class=HTMLResponse)
def list_climbs(request: Request, db: Session = Depends(get_db), message: str | None= None):

    current_user = protect_route(request, db)
    if not current_user:
        return RedirectResponse(url="/login")
 
    # Fetch all climbs
    climbs = db.query(Climb).all()
    # Fetch user interests
    user_interests = {interest.climb_id for interest in current_user.interests}

    return templates.TemplateResponse("areas.html", {
        "request": request,
        "climbs": climbs,
        "message": message,
        "user_interests": user_interests,
        "current_user": current_user
    })

@app.post("/climbs/{climb_id}/interest")
def add_interest(climb_id: str, request: Request, db: Session = Depends(get_db)):

    current_user = protect_route(request, db)
    if not current_user:
        return RedirectResponse(url="/login")

    # Check if the climb exists
    climb = db.query(Climb).filter(Climb.id == climb_id).first()
    if not climb:
        raise HTTPException(status_code=404, detail="Climb not found")

    # Add interest if not already present
    if not any(interest.climb_id == climb_id for interest in current_user.interests):
        new_interest = UserInterest(user_id=current_user.id, climb_id=climb_id)
        feed_item = FeedItem(
                user_id=current_user.id,
                action="new_interest_climb",
                details=f"Started Projecting {climb.name}"
        )
        db.add(feed_item)
        db.add(new_interest)
        db.commit()


    return RedirectResponse(url=f"/area/{climb.area_id}?message=Added climb to your interests", status_code=302)

@app.post("/climbs/{climb_id}/remove")
def remove_interest(
    request: Request,
    climb_id: str,
    db: Session = Depends(get_db),
    completed: str = Form("false")  # Accept 'false' or 'true' as strings
):

    current_user = protect_route(request, db)
    if not current_user:
        return RedirectResponse(url="/login")



    # Convert 'completed' to a boolean
    completed = completed.lower() == "true"

    # Find the interest record
    interest = db.query(UserInterest).filter(
        UserInterest.user_id == current_user.id,
        UserInterest.climb_id == climb_id
    ).first()
    if interest:
        # If completed, create a feed item
        if completed:
            climb = db.query(Climb).filter(Climb.id == climb_id).first()
            feed_item = FeedItem(
                user_id=current_user.id,
                action="completed_climb",
                details=f"Sent {climb.name}"
            )
            db.add(feed_item)

        # Remove the interest
        db.delete(interest)
        db.commit()

    # Redirect to /me with a success message
    message = "Successfully removed climb"
    if completed:
        message = "Successfully marked climb as completed"
    response = RedirectResponse(url=f"/me?message={message}", status_code=302)
    return response

@app.get("/feed", response_class=HTMLResponse)
def user_feed(request: Request, db: Session = Depends(get_db)):

    current_user = protect_route(request, db)
    if not current_user:
        return RedirectResponse(url="/login")


    following = [a.friend for a in current_user.following]

    following_ids = [friend.id for friend in following]
    relevant_user_ids = [current_user.id] + following_ids

    # Fetch feed items for the user and their friends
    feed_items = db.query(FeedItem).filter(
        FeedItem.user_id.in_(relevant_user_ids)
    ).order_by(FeedItem.timestamp.desc()).all()

    return templates.TemplateResponse("feed.html", {
        "request": request,
        "feed_items": feed_items,
        "current_user": current_user
    })

@app.get("/shared-interests", response_class=HTMLResponse)
def shared_interests(request: Request, db: Session = Depends(get_db)):
    current_user = protect_route(request, db)
    if not current_user:
        return RedirectResponse(url="/login")


    user_climbs = db.query(Climb).join(UserInterest).filter(UserInterest.user_id == current_user.id).all()


    shared_interests = {}
    for climb in user_climbs:
        friends_with_interest = (
            db.query(User)
            .join(UserInterest)
            .filter(UserInterest.climb_id == climb.id, User.id.in_([friend.id for friend in current_user.following]))
            .all()
        )
        shared_interests[climb] = friends_with_interest

    return templates.TemplateResponse("shared_interests.html", {
        "request": request,
        "current_user": current_user,
        "shared_interests": shared_interests,
    })

@app.get("/signup", response_class=HTMLResponse)
def signup_form(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})


@app.post("/signup")
def signup(
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create new user
    hashed_password = hash_password(password)
    new_user = User(name=name, email=email, password_hash=hashed_password)
    db.add(new_user)
    db.commit()

    # Redirect to login page with success message
    return RedirectResponse(url="/login?message=Account created successfully. Please log in.", status_code=302)


@app.get("/areas", response_class=HTMLResponse)
def get_areas_page(request: Request, db: Session = Depends(get_db), message: str | None=None):
    areas = db.query(Area).filter(Area.parent_id == None).all()  # Get root areas
    return templates.TemplateResponse("areas.html", {"request": request, "areas": areas, "message": message})

@app.get("/area/{area_id}", response_class=HTMLResponse)
def get_area_details(request: Request, area_id: str, db: Session = Depends(get_db),message: str|None=None):
    # Fetch the selected area by ID
    area = db.query(Area).filter(Area.id == area_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Area not found")

    # Fetch the children of this area
    children = db.query(Area).filter(Area.parent_id == area_id).all()

    # Fetch parent areas (to create breadcrumb)
    breadcrumb = []
    parent = area
    while parent:
        breadcrumb.insert(0, parent)  # Insert at the beginning of the list
        parent = db.query(Area).filter(Area.id == parent.parent_id).first()

    # Fetch climbs for this area if it has no children
    climbs = []
    if not children:
        climbs = db.query(Climb).filter(Climb.area_id == area_id).all()

    # Pass the area, its children, and climbs to the template
    return templates.TemplateResponse("area_details.html", {
        "request": request,
        "area": area,
        "message": message,
        "children": children,
        "climbs": climbs,
        "breadcrumb": breadcrumb
    })


@app.get("/area/{area_id}/add-climb", response_class=HTMLResponse)
def get_add_climb_form(area_id: str, request: Request, db: Session = Depends(get_db)):
    # Fetch the area by ID
    area = db.query(Area).filter(Area.id == area_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Area not found")

    return templates.TemplateResponse("add_climb.html", {"request": request, "area": area})

@app.post("/area/{area_id}/add-climb")
def add_climb(area_id: str, 
              climb_name: str = Form(...), 
              grade_yds: Optional[str] = Form(None), 
              grade_font: Optional[str] = Form(None), 
              description: Optional[str] = Form(None), 
              location: Optional[str] = Form(None), 
              protection: Optional[str] = Form(None), 
              latitude: Optional[str] = Form(None), 
              longitude: Optional[str] = Form(None), 
              db: Session = Depends(get_db)):

    # Convert latitude and longitude to floats, if they are not empty
    parsed_latitude = float(latitude) if latitude and latitude.strip() != "" else None
    parsed_longitude = float(longitude) if longitude and longitude.strip() != "" else None

    area = db.query(Area).filter(Area.id == area_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Area not found")

    # Generate a unique ID for the new climb (UUID can be used for this)
    climb_id = str(uuid.uuid4())

    # Create the new climb
    new_climb = Climb(
        id=climb_id,
        name=climb_name,
        grade_yds=grade_yds,
        grade_font=grade_font,
        description=description,
        location=location,
        protection=protection,
        area_id=area.id,
        latitude=parsed_latitude,
        longitude=parsed_longitude
    )
    
    # Add the climb to the session and commit
    db.add(new_climb)
    db.commit()
    
    # Redirect to the area page
    return RedirectResponse(url=f"/area/{area_id}", status_code=303)



@app.get("/area/{area_id}/add-area", response_class=HTMLResponse)
def get_add_area_form(area_id: str, request: Request, db: Session = Depends(get_db)):
    # Fetch the parent area by ID
    parent_area = db.query(Area).filter(Area.id == area_id).first()
    if not parent_area:
        raise HTTPException(status_code=404, detail="Parent Area not found")

    # Render the form for creating a new area
    return templates.TemplateResponse("add_area.html", {"request": request, "parent_area": parent_area})

@app.post("/area/{area_id}/add-area")
def add_area(area_id: str, 
             name: str = Form(...), 
             latitude: Optional[str] = Form(None), 
             longitude: Optional[str] = Form(None), 
             db: Session = Depends(get_db)):

    # If latitude or longitude is an empty string, set them to None
    parsed_latitude = float(latitude) if latitude is not None and latitude != "" else None
    parsed_longitude = float(longitude) if longitude is not None and longitude != "" else None
    # Fetch the parent area by ID
    parent_area = db.query(Area).filter(Area.id == area_id).first()
    if not parent_area:
        raise HTTPException(status_code=404, detail="Parent Area not found")

    # Generate a unique ID for the new area
    area_id_new = str(uuid.uuid4())
    # Create the new area, associating it with the parent area
    new_area = Area(
        id=area_id_new,
        name=name,
        parent_id=parent_area.id,
        latitude=parsed_latitude,
        longitude=parsed_longitude
    )

    # Add the new area to the session and commit
    db.add(new_area)
    db.commit()

    # Redirect to the parent area page
    return RedirectResponse(url=f"/area/{parent_area.id}", status_code=303)


@app.get("/notifications", response_class=HTMLResponse)
def notifications(request: Request, db: Session = Depends(get_db), message: str | None=None):
    # Protect the route and ensure the user is logged in
    current_user = protect_route(request, db)
    if not current_user:
        return RedirectResponse(url="/login")

    # Fetch notifications for the current user
    notifications = db.query(Notification).filter(
        Notification.user_id == current_user.id
    ).order_by(Notification.timestamp.desc()).all()

    return templates.TemplateResponse("notifications.html", {
        "request": request,
        "current_user": current_user,
        "notifications": notifications,
        "message":message
    })

@app.post("/notifications/{notification_id}/mark-read")
def mark_notification_as_read(notification_id: int, db: Session = Depends(get_db), request: Request = None):
    current_user = protect_route(request, db)
    if not current_user:
        return RedirectResponse(url="/login")

    # Fetch the notification and check if it belongs to the current user
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    if notification.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You cannot mark this notification as read")

    # Mark the notification as read
    notification.read = True
    db.commit()

    return RedirectResponse(url="/notifications", status_code=302)

@app.post("/notifications/{id}/friends")
def add_friend(
    id: int,
    friend_id: int = Form(...),
    db: Session = Depends(get_db),
    request: Request = None
):
    current_user = protect_route(request, db)
    if not current_user:
        return RedirectResponse(url="/login")

    # Ensure the authenticated user is adding friends to their own account
    if current_user.id != id:
        raise HTTPException(status_code=403, detail="You cannot add follows for another user.")

    # Ensure the friend exists
    friend = db.query(User).filter(User.id == friend_id).first()
    if not friend:
        raise HTTPException(status_code=404, detail="User not found")

    # Ensure a user cannot follow themselves
    if current_user.id == friend_id:
        raise HTTPException(status_code=400, detail="You cannot follow yourself.")

    # Check if they're already following this user
    if db.query(UserAssociation).filter(
        UserAssociation.user_id == current_user.id,
        UserAssociation.friend_id == friend_id
    ).first():
        raise HTTPException(status_code=400, detail="You are already following this user.")

    # Add the follow relationship using the UserAssociation model
    new_follow = UserAssociation(
        user_id=current_user.id,
        friend_id=friend_id,
        followed_at=datetime.utcnow()  
    )
    db.add(new_follow)

    # Create a follow notification for the followed user
    notification = Notification(
        user_id=friend_id,
        source_user_id=current_user.id,
        message=f"{current_user.name} started following you.",
        read=False,
        notification_type="follow"
    )
    db.add(notification)
    db.commit()

    # Optionally, create a feed item for the current user (showing who they followed)
    feed_item = FeedItem(
        user_id=current_user.id,
        action="followed",
        details=f"followed {friend.name}"
    )
    db.add(feed_item)
    db.commit()

    return RedirectResponse(url=f"/notifications?message=Successfully added {friend.name} as a friend.", status_code=302)

@app.get("/users/{user_id}", response_class=HTMLResponse)
def user_profile(request: Request, user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user_climbs = db.query(Climb).join(UserInterest).filter(UserInterest.user_id == user.id).all()

    following = db.query(User).join(UserAssociation, UserAssociation.user_id == User.id).filter(UserAssociation.user_id == user.id).all()
    followers = db.query(User).join(UserAssociation, UserAssociation.friend_id == User.id).filter(UserAssociation.friend_id == user.id).all()


    return templates.TemplateResponse(
        "user_profile.html",
        {
            "request": request,
            "user": user,
            "user_climbs": user_climbs,
            "following": following,
            "followers": followers
        }
    )


@app.get("/climb/{climb_id}", response_class=HTMLResponse)
def get_climb_details(request: Request, climb_id: str, db: Session = Depends(get_db)):
    # Fetch the climb by its ID
    climb = db.query(Climb).filter(Climb.id == climb_id).first()
    if not climb:
        raise HTTPException(status_code=404, detail="Climb not found")

    # Fetch users who have this climb as a project (i.e., in their UserInterest)
    users_with_interest = db.query(User).join(UserInterest).filter(UserInterest.climb_id == climb.id).all()

    breadcrumb = []
    parent = climb.area
    while parent:
        breadcrumb.insert(0, parent)  # Insert at the beginning of the list
        parent = db.query(Area).filter(Area.id == parent.parent_id).first()



    return templates.TemplateResponse("climb_details.html", {
        "request": request,
        "climb": climb,
        "users_with_interest": users_with_interest,
        "breadcrumb" : breadcrumb
    })
