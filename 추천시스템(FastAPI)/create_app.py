import os
import sys

TEMPLATE = {
    "router.py": "from fastapi import APIRouter\n\nrouter = APIRouter()\n\n@router.get('/')\ndef read_root():\n    return {\"message\": \"Hello from {name}\"}\n",
    "models.py": "# DB models for {name}\n",
    "schemas.py": "# Pydantic schemas for {name}\n",
    "services.py": "# Business logic for {name}\n",
    "__init__.py": "",
}

def create_app(name):
    base_path = os.path.join("app", name)
    os.makedirs(base_path, exist_ok=True)
    for file, content in TEMPLATE.items():
        with open(os.path.join(base_path, file), "w") as f:
            f.write(content.replace("{name}", name))

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("사용법: python create_app.py [앱이름]")
    else:
        create_app(sys.argv[1])
        print(f"✅ 앱 '{sys.argv[1]}' 생성 완료!")
