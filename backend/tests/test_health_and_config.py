import pytest
from unittest.mock import patch, MagicMock
from app.config import runtime_config

def test_health_not_configured(client):
    runtime_config.cloud_gpu_url = ""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["cloud_gpu_status"] == "not_configured"
    assert data["cloud_gpu_url_set"] is False

def test_health_connected(client):
    runtime_config.cloud_gpu_url = "https://mock-gpu.gradio.live"
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "ok", "gpu": "Tesla T4"}
        mock_get.return_value = mock_resp
        
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["cloud_gpu_status"] == "connected"
        assert data["cloud_gpu_url_set"] is True

def test_health_unreachable(client):
    runtime_config.cloud_gpu_url = "https://mock-gpu.gradio.live"
    with patch("requests.get", side_effect=Exception("Connection refused")):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["cloud_gpu_status"] == "unreachable"

def test_config_never_exposes_raw_gemini_key(client):
    runtime_config.gemini_api_key = "AIzaSySecretKey123456"
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert "has_gemini_key" in data
    assert data["has_gemini_key"] is True
    # The actual secret key must NEVER appear in the response payload
    assert "AIzaSySecretKey123456" not in str(data)

def test_update_cloud_config(client):
    payload = {
        "cloud_gpu_url": "https://custom-colab.gradio.live",
        "gemini_api_key": "new_secret_key",
    }
    response = client.post("/api/config/cloud-gpu", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "updated"
    assert data["cloud_gpu_url"] == "https://custom-colab.gradio.live"
    assert data["has_gemini_key"] is True
    assert runtime_config.cloud_gpu_url == "https://custom-colab.gradio.live"
    assert runtime_config.gemini_api_key == "new_secret_key"

def test_cloud_test_proxy_empty(client):
    runtime_config.cloud_gpu_url = ""
    response = client.post("/api/config/cloud-gpu/test", json={"url": ""})
    assert response.status_code == 400
    data = response.json()
    assert data["status"] == "error"

def test_cloud_test_proxy_success(client):
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"gpu": "Tesla T4", "vram_free_mb": 14000}
        mock_get.return_value = mock_resp
        
        response = client.post("/api/config/cloud-gpu/test", json={"url": "https://test-gpu.gradio.live"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "connected"
        assert data["gpu_info"]["gpu"] == "Tesla T4"

def test_cloud_test_proxy_unreachable(client):
    with patch("requests.get", side_effect=Exception("Timeout")):
        response = client.post("/api/config/cloud-gpu/test", json={"url": "https://unreachable-gpu.gradio.live"})
        assert response.status_code == 502
        data = response.json()
        assert data["status"] == "unreachable"
