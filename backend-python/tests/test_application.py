def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "ClariQ Backend is running!" in data["message"]
    assert "docs" in data


def test_health_endpoint(client):
    response = client.get("/api/health")
    # In test mode with sqlite in-memory, db is connected
    assert response.status_code in (200, 503)
    data = response.json()
    assert "service" in data
    assert "application_status" in data
    assert "environment" in data


def test_database_health_endpoint(client):
    response = client.get("/api/health/database")
    assert response.status_code in (200, 503)
    data = response.json()
    assert "database" in data

    # Test /api/health/db alias
    alias_response = client.get("/api/health/db")
    assert alias_response.status_code in (200, 503)
    assert "database" in alias_response.json()


def test_docs_endpoint(client):
    response = client.get("/docs")
    assert response.status_code == 200
