"""Tests for camera.rtsp_server: RTSPServer pipeline, lifecycle."""

from unittest.mock import MagicMock, patch

import pytest

from camera.rtsp_server import RTSPServer


@pytest.fixture()
def server_config():
    return {
        "rtsp": {
            "enabled": True,
            "port": 8554,
            "path": "/stream",
            "codec": "h264",
            "bitrate": 4000000,
            "keyframe_interval": 30,
        },
        "camera": {
            "width": 1920,
            "height": 1080,
            "fps": 30,
        },
    }


class TestRTSPServer:
    def test_url(self, server_config):
        server = RTSPServer(server_config)
        assert server.url == "rtsp://0.0.0.0:8554/stream"

    def test_url_custom_port(self, server_config):
        server_config["rtsp"]["port"] = 9000
        server_config["rtsp"]["path"] = "/live"
        server = RTSPServer(server_config)
        assert server.url == "rtsp://0.0.0.0:9000/live"

    def test_not_running_initially(self, server_config):
        server = RTSPServer(server_config)
        assert not server.is_running

    def test_build_pipeline_h264(self, server_config):
        server = RTSPServer(server_config)
        pipeline = server._build_pipeline()
        assert "nvv4l2h264enc" in pipeline
        assert "rtph264pay" in pipeline
        assert "1920" in pipeline
        assert "1080" in pipeline

    def test_build_pipeline_h265(self, server_config):
        server_config["rtsp"]["codec"] = "h265"
        server = RTSPServer(server_config)
        pipeline = server._build_pipeline()
        assert "nvv4l2h265enc" in pipeline
        assert "rtph265pay" in pipeline

    @patch("camera.rtsp_server.subprocess.Popen")
    def test_start_launches_process(self, mock_popen, server_config):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # process is running
        mock_popen.return_value = mock_proc

        server = RTSPServer(server_config)
        server.start()

        assert server._running
        mock_popen.assert_called_once()

    @patch("camera.rtsp_server.subprocess.Popen")
    def test_stop_terminates_process(self, mock_popen, server_config):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        server = RTSPServer(server_config)
        server.start()
        server.stop()

        mock_proc.terminate.assert_called_once()
        assert not server._running
        assert server._process is None

    def test_disabled_server_does_not_start(self, server_config):
        server_config["rtsp"]["enabled"] = False
        server = RTSPServer(server_config)
        server.start()
        assert not server.is_running

    @patch("camera.rtsp_server.subprocess.Popen")
    def test_is_running_checks_process(self, mock_popen, server_config):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # Running
        mock_popen.return_value = mock_proc

        server = RTSPServer(server_config)
        server.start()
        assert server.is_running

        mock_proc.poll.return_value = 0  # Exited
        assert not server.is_running

    @patch("camera.rtsp_server.subprocess.Popen", side_effect=FileNotFoundError)
    def test_start_handles_missing_binary(self, mock_popen, server_config):
        server = RTSPServer(server_config)
        server.start()  # Should not raise
        assert not server.is_running
