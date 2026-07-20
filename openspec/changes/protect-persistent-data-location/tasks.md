## 1. Data Location Resolution

- [x] 1.1 Add stable packaged data root, data-location result/source model, and atomic locator persistence
- [x] 1.2 Add lightweight legacy database inspection and deterministic candidate discovery
- [x] 1.3 Enforce override, locator, unique legacy adoption, stable default, and conflict behavior
- [x] 1.4 Add focused path tests for fresh install, changed install path, empty decoy, invalid locator, override, and multi-database conflict

## 2. Startup and Diagnostics

- [x] 2.1 Resolve data location before logging and Repository initialization, with a safe user-facing conflict/error path
- [x] 2.2 Record the selected data root and source in startup logs
- [x] 2.3 Display the selected data root and source in data management settings
- [x] 2.4 Add startup and settings regression tests

## 3. Installer Isolation

- [x] 3.1 Make the Inno AppId and program group overridable for isolated smoke builds
- [x] 3.2 Update release publishing to build/run a smoke installer with a dedicated test identity
- [x] 3.3 Assert that production shortcut and uninstall registration are unchanged by smoke validation
- [x] 3.4 Add release-script regression coverage for production identity isolation

## 4. Verification and Release

- [x] 4.1 Run focused path, startup, settings, and release tests
- [x] 4.2 Run the complete automated test suite and OpenSpec validation
- [x] 4.3 Build v0.6.1 artifacts and run isolated Windows installer smoke validation
- [x] 4.4 Commit and push the implementation checkpoint
- [ ] 4.5 Publish v0.6.1 and verify remote tag, release notes, installer, and archive assets
