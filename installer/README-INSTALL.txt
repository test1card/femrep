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
 Ansys version compatibility (only matters for .rst / .rth)
------------------------------------------------------------
Nastran .f06 files work on any setup. Ansys .rst/.rth files read
through DPF, which is strict about versions:

  Ansys 2022 R2 and newer ... double-click install.bat
  Ansys 2021 R1/R2, 2022 R1 . double-click install-ansys2021.bat

For Ansys 2021/2022R1, use install-ansys2021.bat. It is fully automatic:
it fetches an isolated Python 3.11 just for femrep (your system Python is
NOT changed), pins the compatible DPF 0.9, installs, and makes the icon.
You do not need to install Python yourself for that path.

If reading an Ansys .rst/.rth fails, double-click debug-ansys2021.bat
(or drag the .rst onto it). It reports the Python/DPF versions, the
installed Ansys, and whether the DPF server starts — with the real
error — and saves it to femrep-ansys2021.log for support.

------------------------------------------------------------
 Getting help
------------------------------------------------------------
Project page: https://github.com/test1card/femrep
