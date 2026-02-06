import typer
from agent_sdk.cli.commands import run_cmd, tools_cmd, agents_cmd, init_cmd, serve_cmd
from agent_sdk import docs as docs_module

app = typer.Typer(help="Agent SDK CLI")
app.add_typer(run_cmd, name="run")
app.add_typer(tools_cmd, name="tools")
app.add_typer(agents_cmd, name="agents")
app.add_typer(init_cmd, name="init")
app.add_typer(serve_cmd, name="serve")
app.add_typer(serve_cmd, name="server")


@app.command()
def docs(
    manual: bool = typer.Option(False, "--manual", help="Show user manual"),
    reference: bool = typer.Option(False, "--reference", help="Show quick reference"),
    list_docs: bool = typer.Option(False, "--list", help="List available documentation"),
    info: bool = typer.Option(False, "--info", help="Show documentation info"),
) -> None:
    """Show documentation and help."""
    if manual:
        content = docs_module.get_user_manual()
        if content:
            typer.echo(content)
        else:
            typer.echo("User manual not found", err=True)
    elif reference:
        content = docs_module.get_quick_reference()
        if content:
            typer.echo(content)
        else:
            typer.echo("Quick reference not found", err=True)
    elif list_docs:
        docs_list = docs_module.list_documentation()
        typer.echo(f"Available documentation ({len(docs_list)} files):")
        for doc in sorted(docs_list):
            typer.echo(f"  • {doc}")
    else:
        # Default: show info
        docs_module.print_docs_info()

    app()
