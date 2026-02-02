import typer
from agent_sdk.cli.commands import run_cmd, tools_cmd, agents_cmd, init_cmd, serve_cmd

app = typer.Typer(help="Agent SDK CLI")
app.add_typer(run_cmd, name="run")
app.add_typer(tools_cmd, name="tools")
app.add_typer(agents_cmd, name="agents")
app.add_typer(init_cmd, name="init")
app.add_typer(serve_cmd, name="serve")

def main():
    app()
