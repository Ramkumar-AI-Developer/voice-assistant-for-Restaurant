from app.services.auth_service import hash_password, verify_password

def test_bcrypt():
    password = "admin123"
    hashed = hash_password(password)
    print(f"Password: {password}")
    print(f"Hashed: {hashed}")
    
    match = verify_password(password, hashed)
    print(f"Verification match: {match}")

if __name__ == "__main__":
    test_bcrypt()
