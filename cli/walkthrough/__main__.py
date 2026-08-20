import typer
from dotenv import load_dotenv

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.callback()
def _init() -> None:
    load_dotenv()


@app.command()
def validate() -> None:
    """Schema + cross-checks + anchor drift; fills files[].before/after."""
    raise typer.Exit(2)


if __name__ == "__main__":
    app()
