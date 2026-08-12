import sys
from unittest.mock import patch
from lanmon.security.privileges import check_required_privileges
from unittest.mock import MagicMock

@patch("os.geteuid", return_value=0)
def test_root_has_privileges(mock_geteuid):
    if sys.platform == "win32":
        return
    assert check_required_privileges() is True


@patch("os.geteuid", return_value=1000)
def test_non_root_lacks_privileges(mock_geteuid):
    if sys.platform == "win32":
        return
    assert check_required_privileges() is False

@patch("os.setuid")
@patch("pwd.getpwnam")
def test_drop_privileges_calls_setuid(mock_getpwnam, mock_setuid):
    if sys.platform == "win32":
        return
    mock_pw_entrada = MagicMock()
    mock_pw_entrada.pw_uid = 1000
    mock_getpwnam.return_value = mock_pw_entrada

    from lanmon.security.privileges import drop_privileges
    drop_privileges("nobody")

    mock_getpwnam.assert_called_once_with("nobody")
    mock_setuid.assert_called_once_with(1000)