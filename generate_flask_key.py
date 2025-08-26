from flask_secure_keygen import generate_secret_key

# Generate a 64-character secret key
secret_key = generate_secret_key(64)
print(secret_key)