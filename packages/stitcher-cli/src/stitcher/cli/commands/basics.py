import typer
from needle.pointer import L
from stitcher.common import bus
from stitcher.cli.factories import make_app


def generate_command():
    app_instance = make_app()
    app_instance.run_from_config()


def init_command():
    app_instance = make_app()
    app_instance.run_init()


def strip_command():
    if not typer.confirm(bus.render_to_string(L.strip.run.confirm)):
        bus.warning(L.strip.run.aborted)
        raise typer.Abort()

    app_instance = make_app()
    app_instance.run_strip()


def inject_command():
    if not typer.confirm(bus.render_to_string(L.inject.run.confirm)):
        bus.warning(L.inject.run.aborted)
        raise typer.Abort()

    app_instance = make_app()
    app_instance.run_inject()
