"""Seed script — creates demo users and sample documents via the REST API.

Usage:
    python scripts/seed.py              # uses http://localhost:8000
    python scripts/seed.py http://host  # custom base URL
"""

import sys

import httpx

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"

USERS = [
    {
        "username": "alice",
        "email": "alice@example.com",
        "first_name": "Alice",
        "last_name": "Smith",
        "password": "password123",
    },
    {
        "username": "bob",
        "email": "bob@example.com",
        "first_name": "Bob",
        "last_name": "Jones",
        "password": "password123",
    },
]

DOCUMENTS = [
    {"title": "Getting Started Guide", "owner": "alice@example.com"},
    {"title": "API Reference", "owner": "alice@example.com"},
    {"title": "Architecture Notes", "owner": "bob@example.com"},
]


def register(client: httpx.Client, user: dict) -> None:
    resp = client.post(f"{BASE_URL}/api/auth/register", json=user)
    if resp.status_code == 201:
        print(f"  Registered {user['username']}")
    elif resp.status_code == 409 or resp.status_code == 400:
        print(f"  {user['username']} already exists, skipping")
    else:
        resp.raise_for_status()


def login(client: httpx.Client, email: str, password: str) -> str:
    resp = client.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def create_document(client: httpx.Client, token: str, title: str) -> None:
    resp = client.post(
        f"{BASE_URL}/api/documents",
        json={"title": title},
        headers={"Authorization": f"Bearer {token}"},
    )
    if resp.status_code == 201:
        doc_id = resp.json()["id"]
        print(f"  Created document '{title}' ({doc_id})")
    else:
        resp.raise_for_status()


def main() -> None:
    print(f"Seeding against {BASE_URL}\n")

    with httpx.Client(timeout=10) as client:
        # 1. Register users
        print("Users:")
        for user in USERS:
            register(client, user)

        # 2. Login and cache tokens
        tokens: dict[str, str] = {}
        for user in USERS:
            tokens[user["email"]] = login(client, user["email"], user["password"])

        # 3. Create documents
        print("\nDocuments:")
        for doc in DOCUMENTS:
            create_document(client, tokens[doc["owner"]], doc["title"])

    print("\nDone!")


if __name__ == "__main__":
    main()
