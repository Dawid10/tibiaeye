"""Connection repository config - template images for reconnect detection."""
import pathlib

from ...utils.hash import load_gray_image
from ...utils.image_resolver import resolve_image


CURRENT_PATH = pathlib.Path(__file__).parent.resolve()
IMAGES_PATH = CURRENT_PATH / "images"


def _load(name):
    return load_gray_image(str(resolve_image(IMAGES_PATH, name)))


images = {
    'disconnectDialog': _load("disconnectDialog.png"),
    'okButton': _load("okButton.png"),
    'loginScreen': _load("loginScreen.png"),
    'emailField': _load("emailField.png"),
    'passwordField': _load("passwordField.png"),
    'loginButton': _load("loginButton.png"),
    'characterList': _load("characterList.png"),
    'enterGameButton': _load("enterGameButton.png"),
}
