# Contributing to CheckMyLaptop

Use GitHub Issues for reproducible problems and requests for new diagnostic checks. Include the app version, Windows build, affected check and steps to reproduce. Share only relevant excerpts of reports you have reviewed. Avoid posting raw Windows logs or identifiers.

Run `python -m unittest discover -s tests -v` before opening a pull request. For a new diagnostic rule, include synthetic evidence for both a matching and a nonmatching case. Document the data source, threshold and circumstances where the rule should return an inconclusive result. Keep Windows collection read-only and treat unavailable data as unknown.

## Windows packaging

From a Windows x64 machine with Python 3.12 and Tcl/Tk:

```powershell
py -3.12 -m pip install -r requirements-build.txt
py -3.12 -m PyInstaller --clean --noconfirm --onefile --windowed --name CheckMyLaptop --add-data "checkmylaptop/windows.ps1;checkmylaptop" run_checkmylaptop.py
```

Launch `dist/CheckMyLaptop.exe` and verify a live scan and export on a Windows laptop before sharing a build. Push a matching version tag such as `v0.1.0` to build a release asset. The workflow uploads it to a GitHub draft release for review.
