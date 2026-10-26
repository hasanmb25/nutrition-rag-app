import hashlib
import hmac
import os
import re


ACTIVITY_FACTORS = {
    "Sedentary": 1.2,
    "Lightly active": 1.375,
    "Moderately active": 1.55,
    "Very active": 1.725,
    "Extra active": 1.9,
}


def validate_profile(
    username,
    password,
    age,
    gender_identity,
    height_ft,
    height_in,
    weight_kg,
    activity_level,
    profession,
):
    """Validate account credentials and required profile values."""
    clean_username = username.strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,64}", clean_username):
        raise ValueError(
            "Username must be 3-64 characters and use only letters, digits, dots, "
            "underscores, or hyphens."
        )
    if not 10 <= len(password) <= 128:
        raise ValueError("Password must be between 10 and 128 characters long.")
    if not 18 <= age <= 120:
        raise ValueError("Nutrify profile recommendations are available only for adults (18+).")
    if not gender_identity.strip() or len(gender_identity.strip()) > 80:
        raise ValueError("Please provide your gender identity or select not to say.")
    if not 3 <= height_ft <= 8 or not 0 <= height_in <= 11:
        raise ValueError("Enter a height between 3 feet and 8 feet 11 inches.")
    if not 25 <= weight_kg <= 350:
        raise ValueError("Enter a weight between 25 kg and 350 kg.")
    if activity_level not in ACTIVITY_FACTORS:
        raise ValueError("Choose one of the listed activity levels.")
    if not profession.strip() or len(profession.strip()) > 120:
        raise ValueError("Please enter a profession using no more than 120 characters.")
    return clean_username


def hash_password(password):
    """Hash a password with scrypt and a cryptographically random salt."""
    salt = os.urandom(16)
    password_hash = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=2**14,
        r=8,
        p=1,
        dklen=64,
    )
    return f"scrypt$16384$8$1${salt.hex()}${password_hash.hex()}"


def verify_password(password, encoded_hash):
    """Return whether a password matches a stored scrypt hash."""
    try:
        algorithm, n, r, p, salt_hex, expected_hex = encoded_hash.split("$")
        if algorithm != "scrypt":
            return False
        expected_hash = bytes.fromhex(expected_hex)
        actual_hash = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected_hash),
        )
    except (AttributeError, ValueError):
        return False
    return hmac.compare_digest(actual_hash, expected_hash)
