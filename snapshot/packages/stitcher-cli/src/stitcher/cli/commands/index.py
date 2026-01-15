import typer
from needle.pointer import L
from stitcher.bus import bus
from stitcher.cli.factories import make_app
from stitcher.workspace import WorkspaceNotFoundError


def index_build_command():
    try:
        app_instance = make_app()
    except WorkspaceNotFoundError as e:
        bus.error(L.error.workspace.not_found, path=e.start_path)
        raise typer.Exit(code=1)
    app_instance.run_index_build()
