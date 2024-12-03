import requests
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from database import SessionLocal
from models import Area, Climb

API_URL = "https://api.openbeta.io/graphql"

# Fetch Tennessee areas data from OpenBeta's API
def fetch_openbeta_data():
    query = """
    {
      areas(filter: {area_name: {match: "Tennessee"}}, sort: {}) {
        id
        area_name
        metadata {
          lat
          lng
        }
        children {
          id
          area_name
          metadata {
            lat
            lng
          }
          climbs {
            id
            name
            grades {
              yds
              font
            }
            content {
              description
              location
              protection
            }
            metadata {
              lat
              lng
            }
          }
        }
      }
    }
    """
    response = requests.post(API_URL, json={"query": query})
    return response.json()["data"]

def get_or_create_area(db: Session, area_data, parent_id=None):
    # Check if the area already exists
    existing_area = db.query(Area).filter(Area.id == area_data["id"]).first()
    if existing_area:
        return existing_area
    # Create a new area, setting the parent_id if provided
    new_area = Area(
        id=str(area_data["id"]),
        name=area_data["area_name"],
        latitude=area_data["metadata"].get("lat"),
        longitude=area_data["metadata"].get("lng"),
        parent_id=parent_id  # Set the parent_id
    )
    db.add(new_area)
    db.commit()
    return new_area

# Check if a Climb exists by its ID
def get_or_create_climb(db: Session, climb_data, area_id):
    existing_climb = db.query(Climb).filter(Climb.id == climb_data["id"]).first()
    if existing_climb:
        return existing_climb
    new_climb = Climb(
        id=str(climb_data["id"]),
        name=climb_data["name"],
        grade_yds=climb_data["grades"].get("yds"),
        grade_font=climb_data["grades"].get("font"),
        description=climb_data["content"].get("description"),
        location=climb_data["content"].get("location"),
        protection=climb_data["content"].get("protection"),
        area_id=area_id,
        latitude=climb_data["metadata"].get("lat"),
        longitude=climb_data["metadata"].get("lng"),
    )
    db.add(new_climb)
    db.commit()
    return new_climb

def seed_database():
    db: Session = SessionLocal()
    data = fetch_openbeta_data()

    # Process Areas and Climbs
    for area in data["areas"]:
        # Process the root area (parent)
        parent_area = get_or_create_area(db, area)

        # Process child areas and set their parent_id to the parent area’s id
        for child in area["children"]:
            child_area = get_or_create_area(db, child, parent_id=parent_area.id)

            # Process Climbs under each child area
            for climb in child["climbs"]:
                get_or_create_climb(db, climb, child_area.id)

    db.close()


if __name__ == "__main__":
    seed_database()
