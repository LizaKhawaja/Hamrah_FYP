import hashlib
import secrets
import random 
import math

from datetime import datetime, timezone, timedelta

def hash_pass(password: str) -> str:

    salt = secrets.token_hex(16) 
    salted_password = password + salt
    hashed = hashlib.sha256(salted_password.encode('utf-8')).hexdigest()
    return f"{hashed}${salt}"  # store hash and salt together

def verify(plain_password: str, hash_password: str) -> bool:
    try:
        stored_hash, salt = hash_password.split('$')
        salted_password = plain_password + salt
        computed_hash = hashlib.sha256(salted_password.encode('utf-8')).hexdigest()
        return secrets.compare_digest(computed_hash, stored_hash)
    except Exception:
        return False

def generate_otp() -> str:
    return str(random.randint(100000, 999999))



def otp_expiry_time(minutes: int = 3) -> datetime:
    return datetime.utcnow() + timedelta(minutes=minutes)


# forget pass
def generate_reset_token():
    return secrets.token_urlsafe(32)
    
def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))

def within_time_window(ride_time: datetime, target_time: datetime, margin_minutes: int = 20):
    if ride_time.tzinfo is not None:
        ride_time = ride_time.astimezone().replace(tzinfo=None)
    if target_time.tzinfo is not None:
        target_time = target_time.astimezone().replace(tzinfo=None)
    lower = target_time - timedelta(minutes=margin_minutes)
    upper = target_time + timedelta(minutes=margin_minutes)
    return lower <= ride_time <= upper

def distance_point_to_segment(p_lat, p_lng, a_lat, a_lng, b_lat, b_lng):
    dx = b_lng - a_lng
    dy = b_lat - a_lat
    if dx == 0 and dy == 0:
        return haversine(p_lat, p_lng, a_lat, a_lng), 0.0
    
    t = ((p_lng - a_lng) * dx + (p_lat - a_lat) * dy) / (dx*dx + dy*dy)
    t = max(0.0, min(1.0, t))
    
    c_lat = a_lat + t * dy
    c_lng = a_lng + t * dx
    return haversine(p_lat, p_lng, c_lat, c_lng), t

def is_along_the_way(p_from_lat, p_from_lng, p_to_lat, p_to_lng, route_points, threshold_km=5.0):
    if len(route_points) < 2:
        return False
    
    best_pickup_idx = -1
    best_pickup_t = -1.0
    min_pickup_dist = float('inf')
    
    best_dropoff_idx = -1
    best_dropoff_t = -1.0
    min_dropoff_dist = float('inf')
    
    for i in range(len(route_points) - 1):
        a_lat, a_lng = route_points[i]
        b_lat, b_lng = route_points[i+1]
        
        dist_p, t_p = distance_point_to_segment(p_from_lat, p_from_lng, a_lat, a_lng, b_lat, b_lng)
        if dist_p < min_pickup_dist:
            min_pickup_dist = dist_p
            best_pickup_idx = i
            best_pickup_t = t_p
            
        dist_d, t_d = distance_point_to_segment(p_to_lat, p_to_lng, a_lat, a_lng, b_lat, b_lng)
        if dist_d < min_dropoff_dist:
            min_dropoff_dist = dist_d
            best_dropoff_idx = i
            best_dropoff_t = t_d
            
    if min_pickup_dist <= threshold_km or min_dropoff_dist <= threshold_km:
        if best_pickup_idx < best_dropoff_idx:
            return True
        elif best_pickup_idx == best_dropoff_idx:
            return best_pickup_t < best_dropoff_t
        if best_dropoff_idx < best_pickup_idx and min_dropoff_dist <= threshold_km:
            return True
            
    return False



    


