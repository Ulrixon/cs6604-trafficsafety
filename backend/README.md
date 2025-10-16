# Traffic Safety Index – Mock FastAPI Backend

A minimal FastAPI backend that serves mock traffic‑safety‑index data for intersections.  
The project follows an MVC‑style layout and uses **FastAPI**, **Pydantic**, and **Uvicorn**.

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py               # FastAPI entry point
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py         # Settings (BASE_URL)
│   ├── models/
│   │   ├── __init__.py
│   │   └── intersection.py   # Domain model (dataclass)
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── intersection.py   # Pydantic request/response schemas
│   ├── services/
│   │   ├── __init__.py
│   │   └── intersection_service.py   # In‑memory mock data & business logic
│   └── api/
│       ├── __init__.py
│       └── intersection.py   # FastAPI router (controllers)
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables (optional)
└── Dockerfile                # Optional containerisation
```

## Endpoints

| Method | Path                              | Description                                                                |
| ------ | --------------------------------- | -------------------------------------------------------------------------- |
| `GET`  | `/safety/index/`                  | Returns a list of all intersections with their safety‑index data.          |
| `GET`  | `/safety/index/{intersection_id}` | Returns details for a single intersection identified by `intersection_id`. |
| `GET`  | `/health`                         | Simple health‑check endpoint.                                              |

All responses are JSON and conform to the schemas defined in `backend/app/schemas/intersection.py`.

## Getting Started

### Prerequisites

- Python 3.11 or newer
- `pip` (Python package installer)

### Installation

```bash
# (Optional) Create and activate a virtual environment
python -m venv venv
source venv/bin/activate   # on macOS/Linux
# .\\venv\\Scripts\\activate   # on Windows

# Install dependencies
pip install -r backend/requirements.txt
```

### Running the Server

```bash
uvicorn backend.app.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.  
Open `http://127.0.0.1:8000/docs` in a browser to explore the automatically generated OpenAPI documentation.

### Environment Variables

Create a `.env` file in the project root (or in `backend/`) if you want to override defaults:

```dotenv
BASE_URL=http://localhost:8000
```

The `BASE_URL` value is injected via `backend/app/core/config.py`.

### Docker (optional)

A simple Dockerfile is provided for containerised deployment.

```bash
docker build -t traffic-safety-api .
docker run -p 8000:8000 traffic-safety-api
```

## Testing

You can use any HTTP client (e.g., `curl`, `httpie`, Postman) or the interactive Swagger UI at `/docs`.

Example with `curl`:

```bash
curl http://127.0.0.1:8000/safety/index/
curl http://127.0.0.1:8000/safety/index/101
```

## License

This project is provided for educational purposes and is released under the MIT License.
