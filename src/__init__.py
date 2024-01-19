"""Auxiliar module to run Poetry commands."""
from .sticker_import import app as import_app
from .sticker_pack import app as pack_app
from .sticker_user import app as user_app


def import_pack():
    """Run sticker-import"""
    import_app()

def pack():
    """Run sticker-pack"""
    pack_app()

def user():
    """Run sticker-user"""
    user_app()
