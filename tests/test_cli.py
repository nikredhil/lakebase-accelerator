"""Unit tests for accelerator/cli.py — no credentials needed."""
from __future__ import annotations

from unittest.mock import patch, MagicMock

from accelerator.cli import build_parser, main, _parse_var


class TestParser:
    def test_deploy(self):
        args = build_parser().parse_args(["deploy", "myuc"])
        assert args.cmd == "deploy"
        assert args.name == "myuc"
        assert args.target == "dev"

    def test_plan_with_vars(self):
        args = build_parser().parse_args([
            "plan", "myuc", "--var", "cloud=azure", "--var", "max_workers=1",
        ])
        assert args.cmd == "plan"
        assert args.var == [("cloud", "azure"), ("max_workers", "1")]

    def test_plan_with_vars_file(self):
        args = build_parser().parse_args([
            "plan", "myuc", "--vars-file", "/path/to/vars.json",
        ])
        assert args.vars_file == "/path/to/vars.json"

    def test_plan_with_tags(self):
        args = build_parser().parse_args([
            "deploy", "myuc", "--tags", "team=data,env=dev",
        ])
        assert args.tags == "team=data,env=dev"

    def test_destroy(self):
        args = build_parser().parse_args(["destroy", "myuc"])
        assert args.cmd == "destroy"
        assert args.name == "myuc"

    def test_status(self):
        args = build_parser().parse_args(["status", "myuc"])
        assert args.cmd == "status"

    def test_list(self):
        args = build_parser().parse_args(["list"])
        assert args.cmd == "list"

    def test_target_override(self):
        args = build_parser().parse_args(["deploy", "myuc", "--target", "prod"])
        assert args.target == "prod"


class TestParseVar:
    def test_valid(self):
        assert _parse_var("cloud=azure") == ("cloud", "azure")

    def test_value_with_equals(self):
        assert _parse_var("tag=a=b") == ("tag", "a=b")


class TestMain:
    @patch("accelerator.cli.dab")
    def test_deploy(self, mock_dab):
        mock_dab.deploy.return_value = "cluster-123"
        main(["deploy", "uc1"])
        mock_dab.deploy.assert_called_once()
        call_args = mock_dab.deploy.call_args
        assert call_args[0][0] == "uc1"

    @patch("accelerator.cli.dab")
    def test_destroy(self, mock_dab):
        main(["destroy", "uc1"])
        mock_dab.destroy.assert_called_once_with("uc1", "dev")

    @patch("accelerator.cli.dab")
    def test_list(self, mock_dab):
        mock_dab.list_deployments.return_value = ["uc1", "uc2"]
        main(["list"])
        mock_dab.list_deployments.assert_called_once()

    @patch("accelerator.cli.dab")
    def test_status(self, mock_dab):
        mock_dab.status.return_value = {"state": "deployed"}
        main(["status", "uc1"])
        mock_dab.status.assert_called_once_with("uc1", "dev")
