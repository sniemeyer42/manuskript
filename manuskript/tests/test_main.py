#!/usr/bin/env python
# --!-- coding: utf8 --!--

"""Tests for main.py"""

import os
import signal
import subprocess
import sys
import time

import pytest


def signalIsCaught(pid, sig):
    """Whether the process has a handler for the signal (Linux only)."""
    with open("/proc/{}/status".format(pid)) as f:
        for line in f:
            if line.startswith("SigCgt:"):
                return bool(int(line.split()[1], 16) & (1 << (sig - 1)))
    return False


@pytest.mark.skipif(not sys.platform.startswith("linux"),
                    reason="uses /proc to know when the app is ready")
@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT])
def test_quitOnSignal(sig, tmp_path):
    """
    The application quits when it receives SIGTERM or SIGINT while idle.
    """
    from manuskript import functions as F
    script = F.appPath(os.path.join("bin", "manuskript"))
    if not os.path.isfile(script):
        pytest.skip("bin/manuskript not available")

    # Run in an isolated environment, without any project
    env = dict(os.environ)
    env.update(HOME=str(tmp_path),
               XDG_CONFIG_HOME=str(tmp_path / "config"),
               XDG_DATA_HOME=str(tmp_path / "data"),
               QT_QPA_PLATFORM="offscreen")
    log = tmp_path / "manuskript.log"
    proc = subprocess.Popen([sys.executable, script, "-L", str(log)], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        # Wait until the signal handlers are installed
        deadline = time.monotonic() + 60
        while not signalIsCaught(proc.pid, signal.SIGTERM):
            assert proc.poll() is None, "manuskript exited during startup"
            assert time.monotonic() < deadline, "manuskript did not start"
            time.sleep(0.1)
        # Let it reach the (idle) event loop
        time.sleep(0.5)

        proc.send_signal(sig)
        assert proc.wait(timeout=10) == 0
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()

    assert "received. Quitting..." in log.read_text()


# Runs manuskript with a project that has unsaved changes and "save on quit"
# turned off, closes the main window (like its close button, or with a first
# SIGTERM), sends SIGTERM while the "Save project?" question is shown, and
# then answers "Save".
SAVE_PROMPT_DRIVER = """
import os, signal, sys
root, project, log, firstClose = sys.argv[1:5]
sys.path.insert(0, root)
sys.argv = [sys.argv[0], "-L", log, project]
from manuskript import main

def launch(arguments, app, MW=None):
    from PyQt5.QtCore import QTimer
    from PyQt5.QtWidgets import qApp, QMessageBox
    from manuskript import settings

    def prompt():
        w = qApp.activeModalWidget()
        return w if isinstance(w, QMessageBox) and w.isVisible() else None

    def signalAtPrompt():
        print("PROMPT" if prompt() else "NO PROMPT", flush=True)
        os.kill(os.getpid(), signal.SIGTERM)

    def answer():
        if prompt():
            print("STILL ASKING", flush=True)
            prompt().button(QMessageBox.Save).click()

    def start():
        if not MW.currentProject:
            QTimer.singleShot(100, start)
            return
        settings.saveOnQuit = False
        settings.autoSaveNoChanges = False
        MW.mdlFlatData.item(1, 0).setText("UNSAVED EDIT")
        MW.projectDirty = True
        QTimer.singleShot(500, signalAtPrompt)
        QTimer.singleShot(2000, answer)
        if firstClose == "signal":
            os.kill(os.getpid(), signal.SIGTERM)
        else:
            MW.close()

    QTimer.singleShot(0, start)
    main_launch(arguments, app, MW)

main_launch = main.launch
main.launch = launch
main.run()
print("RUN RETURNED", flush=True)
"""


@pytest.mark.skipif(not sys.platform.startswith("linux"),
                    reason="needs POSIX signals, and an isolated HOME only "
                           "isolates the settings on Linux")
@pytest.mark.parametrize("firstClose", ["window", "signal"])
def test_signalWhileAskingToSave(firstClose, tmp_path):
    """
    A signal received while the main window asks whether to save the project
    must not quit the application: that would dismiss the question as if
    the user chose "Discard", and the changes would be lost.
    """
    import shutil
    from manuskript import functions as F
    root = F.appPath()
    spDir = F.appPath("sample-projects")
    project = tmp_path / "book-of-acts.msk"
    shutil.copyfile(os.path.join(spDir, "book-of-acts.msk"), str(project))
    shutil.copytree(os.path.join(spDir, "book-of-acts"), str(project)[:-4])

    # Keep the real settings untouched: main.run() uses the real
    # organization name (CFFIXED_USER_HOME is the macOS equivalent of HOME)
    env = dict(os.environ)
    env.update(HOME=str(tmp_path),
               CFFIXED_USER_HOME=str(tmp_path),
               XDG_CONFIG_HOME=str(tmp_path / "config"),
               XDG_DATA_HOME=str(tmp_path / "data"),
               QT_QPA_PLATFORM="offscreen")
    log = tmp_path / "manuskript.log"
    proc = subprocess.run([sys.executable, "-c", SAVE_PROMPT_DRIVER, root,
                           str(project), str(log), firstClose],
                          env=env, cwd=str(tmp_path), timeout=60,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          universal_newlines=True)
    output = proc.stdout

    assert "PROMPT\n" in output, output
    assert "STILL ASKING\n" in output, output
    assert "RUN RETURNED\n" in output, output
    assert proc.returncode == 0, output
    # The changes were saved (auto-saving is off in the driver)
    saved = ""
    for path, dirs, files in os.walk(str(project)[:-4]):
        for name in files:
            with open(os.path.join(path, name), encoding="utf8") as f:
                saved += f.read()
    assert "UNSAVED EDIT" in saved
