import asyncio
import os
import sys

# Add project root to sys.path
sys.path.append(os.getcwd())

from backend.core.settings import get_settings
from backend.core.auth import create_access_token, verify_password, get_password_hash
from backend.core.passwords import hash_password as hash_legacy

async def main():
    settings = get_settings()
    print(f"Testing JWT implementation...")
    print(f"Admin User: {settings.admin_username}")
    
    # Test Password Hashing & Verification
    test_pass = "my_secret_password"
    
    # 1. Test Legacy Hash
    legacy_hash = hash_legacy(test_pass)
    assert verify_password(test_pass, legacy_hash), "Legacy hash verification failed!"
    print("✅ Legacy PBKDF2 verification: OK")
    
    # 2. Test New Bcrypt Hash
    new_hash = get_password_hash(test_pass)
    assert verify_password(test_pass, new_hash), "Bcrypt hash verification failed!"
    print("✅ New Bcrypt verification: OK")
    
    # 3. Test JWT Generation
    token = create_access_token(data={"sub": "testuser"})
    print(f"✅ JWT Generation: OK (Token length: {len(token)})")
    
    print("\nTo test the API endpoint via Curl (when server is running):")
    cmd = f"curl -X POST http://localhost:8000/auth/token -H 'Content-Type: application/x-www-form-urlencoded' -d 'username={settings.admin_username}&password={settings.admin_password}'"
    print(cmd)

if __name__ == "__main__":
    asyncio.run(main())