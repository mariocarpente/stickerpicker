# maunium-stickerpicker - A fast and simple Matrix sticker picker widget.
# Copyright (C) 2020 Tulir Asokan
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
from typing import Dict, Optional
from hashlib import sha256
import mimetypes
import os.path
import asyncio
import string
import requests
import json
import typer  # Importa la librería Typer

try:
    import magic
except ImportError:
    print("[Warning] Magic is not installed, using file extensions to guess mime types")
    magic = None

from .lib import matrix, util

app = typer.Typer()

def convert_name(name: str) -> str:
    name_translate = {
        ord(" "): ord("_"),
    }
    allowed_chars = string.ascii_letters + string.digits + "_-/.#"
    return "".join(filter(lambda char: char in allowed_chars, name.translate(name_translate)))


async def upload_sticker(file: str, directory: str, old_stickers: Dict[str, matrix.StickerInfo]
                         ) -> Optional[matrix.StickerInfo]:
    if file.startswith("."):
        return None
    path = os.path.join(directory, file)
    if not os.path.isfile(path):
        return None

    if magic:
        mime = magic.from_file(path, mime=True)
    else:
        mime, _ = mimetypes.guess_type(file)
    if not mime.startswith("image/"):
        return None

    print(f"Processing {file}", end="", flush=True)
    try:
        with open(path, "rb") as image_file:
            image_data = image_file.read()
    except Exception as e:
        print(f"... failed to read file: {e}")
        return None
    name = os.path.splitext(file)[0]

    # If the name starts with "number-", remove the prefix
    name_split = name.split("-", 1)
    if len(name_split) == 2 and name_split[0].isdecimal():
        name = name_split[1]

    sticker_id = f"sha256:{sha256(image_data).hexdigest()}"
    print(".", end="", flush=True)
    if sticker_id in old_stickers:
        sticker = {
            **old_stickers[sticker_id],
            "body": name,
        }
        print(f".. using existing upload")
    else:
        image_data, width, height = util.convert_image(image_data)
        print(".", end="", flush=True)
        mxc = await matrix.upload(image_data, "image/png", file)
        print(".", end="", flush=True)
        sticker = util.make_sticker(mxc, width, height, len(image_data), name)
        sticker["id"] = sticker_id
        print(" uploaded", flush=True)
    return sticker


async def main(config: str, write_conf: Optional[bool], homeserver: Optional[str], access_token: Optional[str], title: Optional[str], id: Optional[str], add_to_packs: Optional[str], path: str) -> None:
    await matrix.load_config(config, write_conf, homeserver, access_token)

    dirname = os.path.basename(os.path.abspath(path))
    meta_path = os.path.join(path, "pack.json")
    try:
        with util.open_utf8(meta_path) as pack_file:
            pack = json.load(pack_file)
            print(f"Loaded existing pack meta from {meta_path}")
    except FileNotFoundError:
        pack = {
            "title": title or dirname,
            "id": id or convert_name(dirname).lower(),
            "stickers": [],
        }
        old_stickers = {}
    else:
        old_stickers = {sticker["id"]: sticker for sticker in pack["stickers"]}
        pack["stickers"] = []

    for file in sorted(os.listdir(path)):
        sticker = await upload_sticker(file, path, old_stickers=old_stickers)
        if sticker:
            pack["stickers"].append(sticker)

    with util.open_utf8(meta_path, "w") as pack_file:
        json.dump(pack, pack_file)
    print(f"Wrote pack to {meta_path}")

    if add_to_packs:
        picker_file_name = f"{pack['id']}.json"
        picker_pack_path = os.path.join(add_to_packs, picker_file_name)
        with util.open_utf8(picker_pack_path, "w") as pack_file:
            json.dump(pack, pack_file)
        print(f"Copied pack to {picker_pack_path}")
        util.add_to_index(picker_file_name, 'web/users/')


@app.command("upload", help="Manage sticker packs")
def upload_command(
    config: str = typer.Option("config.json", help="Path to JSON file with Matrix homeserver and access_token"),
    write_conf: bool = typer.Option(False, help="Write JSON with configuration to the path specified in --config"),
    homeserver: str = typer.Option(None, help="Homeserver URL. Example: https://example.com"),
    access_token: str = typer.Option(None, help="User access token"),
    title: Optional[str] = typer.Option(None, help="Override the sticker pack displayname. Default folder name"),
    id: Optional[str] = typer.Option(None, help="Override the sticker pack ID. Default folder name"),
    path: str = typer.Argument(..., help="Path to the sticker pack directory")
) -> None:
    if (homeserver == None and access_token != None) or  (homeserver != None and access_token == None) :
        typer.echo("ERROR: The homeserver and access token must be sent together.")
        raise typer.Exit(code=1)
    elif write_conf and (homeserver == None or access_token == None):
        typer.echo("ERROR: To write config file the homeserver and access token must be sent together.")
        raise typer.Exit(code=1)
    if id:
        id = id.lower()
    add_to_packs = 'web/users/packs/'
    asyncio.get_event_loop().run_until_complete(main(config, write_conf, homeserver, access_token, title, id, add_to_packs, path))


def find_pack_folder(pack_id: str, current_path: str = "packs") -> Optional[str]:
    for root, dirs, files in os.walk(current_path):
        for folder in dirs:
            pack_path = os.path.join(root, folder)
            pack_json_path = os.path.join(pack_path, "pack.json")

            if os.path.exists(pack_json_path):
                with open(pack_json_path, "r") as pack_file:
                    pack_data = json.load(pack_file)
                    if "id" in pack_data and pack_data["id"].lower() == pack_id.lower():
                        return pack_path

    return None


def get_next_order_number(pack_path: str) -> str:
    order_numbers = set()

    for filename in os.listdir(pack_path):
        if filename.lower() == "pack.json":
            continue

        try:
            order = int(filename.split("-")[0])
            order_numbers.add(order)
        except (ValueError, IndexError):
            continue

    order_numbers = sorted(order_numbers)
    for order in range(1, len(order_numbers) + 2):
        if order not in order_numbers:
            return str(order).zfill(2)

    return str(len(order_numbers) + 1).zfill(2)


def download_image(image_url: str, destination: str) -> None:
    response = requests.get(image_url)
    if response.status_code == 200:
        with open(destination, "wb") as image_file:
            image_file.write(response.content)
    else:
        print(f"ERROR: Failed to download image from {image_url}")
        raise typer.Exit(code=1)


@app.command("add-image", help="Add image to pack")
def add_image_command(
    pack_id: str = typer.Argument(..., help="Pack id"),
    name: str = typer.Argument(..., help="Image name"),
    image_url: Optional[str] = typer.Option(None, help="Image URL to download"),
    image_path: Optional[str] = typer.Option(None, help="Path to local image file"),
) -> None:
    if image_url:
        image_extension = image_url.split(".")[-1].lower()
    elif image_path and os.path.isfile(image_path):
        image_extension = image_path.split(".")[-1].lower()
    else:
        print("ERROR: Please provide either an image URL or a local image file path.")
        raise typer.Exit(code=1)

    pack_path = find_pack_folder(pack_id)

    if not pack_path:
        print(f"ERROR: No pack found with id {pack_id}. Please create the pack first.")
        raise typer.Exit(code=1)

    next_order_number = get_next_order_number(pack_path)

    if image_extension not in {"jpg", "jpeg", "png", "gif"}:
        print("ERROR: Invalid image format. Supported formats: jpg, jpeg, png, gif")
        raise typer.Exit(code=1)

    image_filename = f"{next_order_number}-{name.replace(' ', '-')}.{image_extension}"
    image_destination = os.path.join(os.path.abspath(pack_path), image_filename)
    if image_url:
        msg = download_image(image_url, image_destination)
    elif image_path and os.path.isfile(image_path):
        with open(image_path, "rb") as file:
            image_data = file.read()
        with open(image_destination, "wb") as file:
            file.write(image_data)
    if msg:
        print(msg)
    else:
        print(f"Image {name} added to pack {pack_id} as {image_filename}")


@app.command("create", help="Create a new sticker pack")
def create_command(
    name: str = typer.Argument(..., help="Name of the new pack"),
    title: str = typer.Argument(..., help="Title of the new pack"),
    id: Optional[str] = typer.Option(None, help="ID of the new pack (defaults to name)"),
) -> None:
    name = name.lower()
    pack_path = os.path.join(os.path.abspath("packs"), name)

    if os.path.exists(pack_path):
        print(f"Error: Pack '{name}' already exists.")
        raise typer.Exit(code=1)

    pack_id = id.lower().replace(' ', '-') if id else name
    os.makedirs(pack_path)

    # Crear el contenido del archivo pack.json
    pack_data = {"id": pack_id, "title": title, "stickers": []}

    # Crear el archivo pack.json en la carpeta del pack
    with open(os.path.join(pack_path, "pack.json"), "w", encoding="utf-8") as pack_file:
        json.dump(pack_data, pack_file, ensure_ascii=False, indent=2)

    print(f"Sticker pack '{name}' created successfully with ID '{pack_id}' and title '{title}'.")


def list_available_packs(index_path: str = 'web/users/index.json', packs_dir: str = 'packs'):
    try:
        with open(index_path, 'r', encoding='utf-8') as index_file:
            index_data = json.load(index_file)
        installed_packs = index_data.get('packs', [])
        installed_packs = list(map(lambda x: x.replace('.json', ''), installed_packs))
    except FileNotFoundError:
        typer.echo(f"El archivo {index_path} no existe.")
        installed_packs = []

    all_packs = []
    for root, dirs, files in os.walk(packs_dir):
        for folder in dirs:
            pack_path = os.path.join(root, folder)
            pack_json_path = os.path.join(pack_path, "pack.json")

            if os.path.exists(pack_json_path):
                with open(pack_json_path, "r") as pack_file:
                    pack_data = json.load(pack_file)
                    all_packs.append(pack_data["id"])

    not_installed_packs = [pack for pack in all_packs if pack.lower() not in installed_packs]

    typer.echo("Installed packs:")
    for i, pack in enumerate(installed_packs, start=1):
        typer.echo(f"{i}. {pack}")

    typer.echo("\nNot installed packs:")
    for pack in not_installed_packs:
        typer.echo(f"* {pack}")


@app.command("list", help="List installed and not installed sticker packs")
def list_command(
    index_path: str = typer.Option('web/users/index.json', help="Path to index.json file"),
    packs_dir: str = typer.Option('packs', help="Path to packs directory")
):
    list_available_packs(index_path, packs_dir)


if __name__ == "__main__":
    app()
