============================================================
 femrep — how to install (Windows)
============================================================

femrep turns Ansys / Nastran result files (.rst, .rth, .f06)
into standardized PDF / DOCX engineering reports.

You do NOT need git or any programming knowledge.

------------------------------------------------------------
 STEP 1 — Make sure Python is installed
------------------------------------------------------------
femrep runs on Python 3.10 to 3.12 (3.12 recommended).

If you are not sure whether you have Python, just run the
installer in Step 2 — it will tell you and give instructions
if Python is missing.

To install Python yourself:
  - Open the Microsoft Store, search "Python 3.12", click Get.
    (easiest — nothing else to configure)
  - OR download from https://www.python.org/downloads/
    On the installer screen, TICK "Add python.exe to PATH"
    before clicking Install.

------------------------------------------------------------
 STEP 2 — Run the installer
------------------------------------------------------------
  1. Keep this whole folder together (do not move just the
     install.bat out on its own — it needs the .whl file
     next to it).
  2. Double-click  install.bat
  3. A black window opens and shows progress. The first run
     downloads packages and can take a few minutes.
  4. When it says "Done!", close the window.

A "femrep" icon appears on your Desktop.

------------------------------------------------------------
 STEP 3 — Use femrep
------------------------------------------------------------
Double-click the "femrep" icon on your Desktop to open the
graphical app.

If Windows SmartScreen warns about the .bat file, click
"More info" then "Run anyway" — this is normal for scripts
that are not signed by a big vendor.

------------------------------------------------------------
 To uninstall
------------------------------------------------------------
Double-click  uninstall.bat  in this folder. It removes the
femrep environment and the Desktop icon. It does not touch
your Python or your Ansys installation.

------------------------------------------------------------
 Getting help
------------------------------------------------------------
Project page: https://github.com/test1card/femrep
