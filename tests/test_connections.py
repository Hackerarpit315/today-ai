from app.integrations.connections.manager import connection_manager
from app.integrations.connections.models import ConnectionStatus


def test_connect_user_provider():
    connection_manager.remove(
        user_id="connection-test-user",
        provider="google",
    )

    connection = connection_manager.connect(
        user_id="connection-test-user",
        provider="google",
        services=["calendar"],
    )

    assert connection.user_id == "connection-test-user"
    assert connection.provider == "google"
    assert connection.services == ["calendar"]
    assert connection.status == ConnectionStatus.CONNECTED


def test_get_connection_status():
    connection_manager.remove(
        user_id="status-test-user",
        provider="google",
    )

    connection_manager.connect(
        user_id="status-test-user",
        provider="google",
        services=["calendar"],
    )

    status = connection_manager.status(
        user_id="status-test-user",
        provider="google",
    )

    assert status == ConnectionStatus.CONNECTED


def test_list_user_connections():
    connection_manager.remove(
        user_id="list-test-user",
        provider="google",
    )

    connection_manager.connect(
        user_id="list-test-user",
        provider="google",
        services=["calendar", "drive"],
    )

    connections = connection_manager.list_connections(
        user_id="list-test-user",
    )

    assert len(connections) == 1
    assert connections[0].provider == "google"
    assert connections[0].services == ["calendar", "drive"]


def test_disconnect_connection():
    connection_manager.remove(
        user_id="disconnect-test-user",
        provider="google",
    )

    connection_manager.connect(
        user_id="disconnect-test-user",
        provider="google",
        services=["calendar"],
    )

    result = connection_manager.disconnect(
        user_id="disconnect-test-user",
        provider="google",
    )

    assert result is True

    status = connection_manager.status(
        user_id="disconnect-test-user",
        provider="google",
    )

    assert status == ConnectionStatus.DISCONNECTED


def test_unknown_connection_is_disconnected():
    connection_manager.remove(
        user_id="unknown-test-user",
        provider="google",
    )

    status = connection_manager.status(
        user_id="unknown-test-user",
        provider="google",
    )

    assert status == ConnectionStatus.DISCONNECTED


def test_user_connections_are_isolated():
    connection_manager.remove(
        user_id="user-a",
        provider="google",
    )
    connection_manager.remove(
        user_id="user-b",
        provider="google",
    )

    connection_manager.connect(
        user_id="user-a",
        provider="google",
        services=["calendar"],
    )

    user_a_connections = connection_manager.list_connections(
        user_id="user-a",
    )
    user_b_connections = connection_manager.list_connections(
        user_id="user-b",
    )

    assert len(user_a_connections) == 1
    assert len(user_b_connections) == 0