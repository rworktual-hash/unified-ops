from app.models.server import Server


def ssh_kwargs_from_server(server: Server) -> dict:
    return {
        "host": server.ip_address,
        "port": server.ssh_port,
        "username": server.ssh_username,
        "credential_ref": server.credential_ref,
        "ssh_password": server.ssh_password,
        "ssh_auth_mode": server.ssh_auth_mode or "auto",
    }
