import os
import sys

def check_required_privileges() -> bool:
    if sys.platform == "win32":
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    return os.geteuid() == 0

def drop_privileges(target_user: str) -> None:
    if sys.platform == "win32":
        return
    import pwd
    user_entrada = pwd.getpwnam(target_user)
    os.setuid(user_entrada.pw_uid)