"""
Error Messages - Maps technical errors to user-friendly messages.
"""
import re

_ERROR_PATTERNS = [
    (
        r"(?i)screenshot returned none|capture\(\) returned none|screenshot is none",
        "Captura de tela falhou.",
        "Verifique se a janela do Tibia esta visivel e nao minimizada.",
    ),
    (
        r"(?i)battle\s?list not found|battlelist not detected",
        "Battle List nao detectada.",
        "Abra o Tibia e certifique-se de que o Battle List esta visivel no jogo.",
    ),
    (
        r"(?i)arduino.*connect|serial.*connect|could not open port",
        "Arduino desconectado.",
        "Verifique o cabo USB e a porta serial.",
    ),
    (
        r"(?i)coordinate extraction failed|radar.*failed|could not read coordinate",
        "Radar nao legivel.",
        "Verifique se o minimapa esta no zoom correto (sem zoom in/out).",
    ),
    (
        r"(?i)serial write failed|serial.*write.*error",
        "Falha ao enviar comando para Arduino.",
        "Reconecte o dispositivo USB.",
    ),
    (
        r"(?i)skills window not|skills.*not detected",
        "Janela de Skills nao detectada.",
        "Abra a janela Skills no Tibia (Ctrl+S).",
    ),
    (
        r"(?i)license.*expired",
        "Licenca expirada.",
        "Renove sua assinatura em tibiaeye.com.",
    ),
    (
        r"(?i)license.*invalid",
        "Licenca invalida.",
        "Verifique sua chave de API no arquivo .env.",
    ),
    (
        r"(?i)websocket.*closed|ws.*disconnect|realtime.*disconnect",
        "Conexao de telemetria perdida.",
        "O bot continuara funcionando. A telemetria sera reconectada automaticamente.",
    ),
    (
        r"(?i)NoneType.*has no attribute|AttributeError.*None",
        "Erro interno: dados nao disponiveis.",
        "Verifique se a janela do Tibia esta visivel e tente reiniciar o bot.",
    ),
]

_COMPILED_PATTERNS = [(re.compile(p), msg, sug) for p, msg, sug in _ERROR_PATTERNS]


def friendly_error(technical_message):
    """Convert a technical error message to a user-friendly tuple.

    Returns:
        (user_message, suggestion) if a pattern matches, else (original_message, None).
    """
    text = str(technical_message)
    for pattern, message, suggestion in _COMPILED_PATTERNS:
        if pattern.search(text):
            return message, suggestion
    return text, None
