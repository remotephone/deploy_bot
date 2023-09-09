import subprocess
from unittest.mock import Mock
import pytest
from deploy_bot import (
    deploy_docker_stack_on_host,
    get_docker_service_logs,
    get_running_containers,
)


@pytest.fixture
def subprocess_run(mocker):
    return mocker.patch("subprocess.run", autospec=True)


@pytest.fixture
def open_mock(mocker):
    return mocker.patch(
        "builtins.open",
        mocker.mock_open(
            read_data='{"my_service": {"compose_file": "my_compose.yml", "service_name": "my_service", "with_reg_auth": true, "remove_first": false}, "my_service_remove_first": {"compose_file": "my_service_remove_first_compose.yml", "service_name": "my_service_remove_first", "with_reg_auth": true, "remove_first": true}}'
        ),
    )


def test_get_docker_service_logs_success(subprocess_run):
    subprocess_run.return_value = Mock(returncode=0, stdout=b"Log output")

    result = get_docker_service_logs("my_service")

    assert result == b"Log output"
    subprocess_run.assert_called_once_with(
        ["docker", "service", "logs", "my_service"], stdout=subprocess.PIPE
    )


def test_get_docker_service_logs_failure(subprocess_run):
    subprocess_run.return_value = Mock(returncode=1, stdout=b"Error message")

    result = get_docker_service_logs("my_service")

    assert result == b"Error message"
    subprocess_run.assert_called_once_with(
        ["docker", "service", "logs", "my_service"], stdout=subprocess.PIPE
    )
    # You can also assert that deploy_logger.error was called with the correct message


def test_get_running_containers_success(subprocess_run):
    subprocess_run.return_value = Mock(
        returncode=0, stdout=b'[{"ID": "container_id", "Name": "container_name"}]'
    )

    result = get_running_containers("my_service")

    assert result == b'[{"ID": "container_id", "Name": "container_name"}]'
    subprocess_run.assert_called_once_with(
        [
            "docker",
            "service",
            "ps",
            "my_service",
            "--filter",
            "desired-state=running",
            "--format",
            "json",
        ],
        stdout=subprocess.PIPE,
    )


def test_get_running_containers_failure(subprocess_run):
    subprocess_run.return_value = Mock(returncode=1, stdout=b"Error message")

    result = get_running_containers("my_service")

    assert result == b"Error message"
    subprocess_run.assert_called_once_with(
        [
            "docker",
            "service",
            "ps",
            "my_service",
            "--filter",
            "desired-state=running",
            "--format",
            "json",
        ],
        stdout=subprocess.PIPE,
    )
    # You can also assert that deploy_logger.error was called with the correct message


def test_deploy_docker_stack_on_host_found_service_with_reg_auth(
    subprocess_run, open_mock, mocker
):
    subprocess_run.return_value = Mock(returncode=0, stdout=b"Deployment successful")

    result = deploy_docker_stack_on_host("my_service")

    assert result == "Deployment successful"
    open_mock.assert_called_once_with("/opt/deploy_bot/services.yml")
    subprocess_run.assert_called_once_with(
        [
            "docker",
            "stack",
            "deploy",
            "--with-registry-auth",
            "-c",
            "my_compose.yml",
            "my_service",
        ],
        stdout=subprocess.PIPE,
    )
    # You can also assert that deploy_logger.info was called with the correct messages


def test_deploy_docker_stack_on_host_found_service_remove_first(
    subprocess_run, open_mock, mocker
):
    subprocess_run.return_value = Mock(returncode=0, stdout=b"Deployment successful")

    result = deploy_docker_stack_on_host("my_service_remove_first")

    assert result == "Deployment successful"
    open_mock.assert_called_once_with("/opt/deploy_bot/services.yml")
    subprocess_run.assert_called_once_with(
        [
            "docker",
            "service",
            "rm",
            "my_service_remove_first",
            "&&",
            "docker",
            "stack",
            "deploy",
            "--with-registry-auth",
            "-c",
            "my_service_remove_first_compose.yml",
            "my_service_remove_first",
        ],
        stdout=subprocess.PIPE,
    )
    # You can also assert that deploy_logger.info was called with the correct messages


def test_deploy_docker_stack_on_host_service_not_found(
    subprocess_run, open_mock, mocker
):
    result = deploy_docker_stack_on_host("nonexistent_service")

    assert result == "Service not found"
    open_mock.assert_called_once_with("/opt/deploy_bot/services.yml")
    subprocess_run.assert_not_called()
    # You can also assert that deploy_logger.error was called with the correct message
