import typer
import os
import asyncio
from pathlib import Path
from typing import List, Optional, Annotated

from .lib import util, matrix

app = typer.Typer()

def add_packs_to_user(username: str, packs: List[Path], output_dir: str = "web/users") -> None:
    for pack in packs:
        pack_json_path = os.path.join(output_dir, f"packs/{pack.stem}.json")

        if os.path.isfile(pack_json_path):
            util.add_to_index(pack.stem, output_dir,f"{username}.json")
        else:
            print(f"Pack {pack.stem} not found in {output_dir}")
            raise typer.Exit(code=1)


def del_packs_to_user(username: str, packs: List[Path], output_dir: str = "web/users") -> None:
    for pack in packs:
        util.remove_from_index(pack.stem, output_dir,f"{username}.json")


@app.command("add-packs", help="Add packs to user's sticker config")
def add_command(
    packs: List[Path] = typer.Argument(..., help="Name of the packs to add to the user"),
    username: str = typer.Option(..., help="Element User Name", metavar="User name"),
):
    add_packs_to_user(username, packs)


@app.command("del-packs", help="Delete packs to user's sticker config")
def del_command(
    packs: List[Path] = typer.Argument(..., help="Name of the packs to delete to the user"),
    username: str = typer.Option(..., help="Element User Name", metavar="User name"),
):
    del_packs_to_user(username, packs)


@app.command("install", help="Install Stickerpicker in user account")
def install_command(
    sticker_server: str = typer.Argument(..., help="Path to the sticker website displayed. Example: domain.example.com/stickers"),
    homeserver: str = typer.Argument(..., help="Homeserver Domain. Example: example.com"),
    username: str = typer.Argument(..., help="Element User Name"),
    access_token: str = typer.Argument(..., help="User Access token"),
    port: Optional[str] = typer.Option('8448', help="Synapse port"),
    selected:  Annotated[bool, typer.Option("--selected/--all", "-s/-a", help="Install only selected user packs.")] = False) -> None:
    try:
        user_param = ''
        if selected:
            user_param = '&user={username}'

        body = {
            "stickerpicker": {
                "content": {
                    "type": "m.stickerpicker",
                    "url": f"https://{sticker_server}/?theme=$theme{user_param}",
                    "name": "Stickerpack",
                    "data": {}
                },
                "sender": f"@{username}:{homeserver}",
                "state_key": "stickerpicker",
                "type": "m.widget",
                "id": "stickerpicker"
            }
        }
        asyncio.get_event_loop().run_until_complete(matrix.send_event_widget(body, username, homeserver, access_token, port))
        print(f"Stickerpicker installed successfully for user {username}")
    except Exception as e:
        print(f"ERROR: Failed to install Stickerpicker: {e}")
        raise typer.Exit(code=1)


@app.command("uninstall", help="Uninstall Stickerpicker in user account")
def uninstall_command(
    username: str = typer.Argument(..., help="Element User Name"),
    access_token: str = typer.Argument(..., help="User Access token"),
    homeserver: str = typer.Argument(..., help="Homeserver Domain. Example: example.com"),
    port: Optional[str] = typer.Option('8448', help="Synapse port")) -> None:
    try:
        body = {}
        asyncio.get_event_loop().run_until_complete(matrix.send_event_widget(body, username, homeserver, access_token, port))
        print(f"Stickerpicker uninstalled successfully for user {username}")
    except Exception as e:
        print(f"ERROR: Failed to uninstall Stickerpicker: {e}")
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()
