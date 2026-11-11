# Browser CI environment — 2026-11-11

Browser verification was blocked before executing the application. Jobs
130606309341 and 130617193355 failed while installing Playwright's OS packages:
DNS resolution of security.ubuntu.com and archive.ubuntu.com failed. Retry
130614643183 encountered the same failure before a newer verification superseded it.

The existing browser job now uses Microsoft's Playwright 1.63.0 Noble image,
matching the repository's locked Playwright dependency. Browsers and their system
libraries are already present. The Ubuntu 24.04 host matches the container's
distribution for the setup-python toolcache; Python 3.12 remains available for
the delivery builder. Shared memory is bounded to 1 GiB without host IPC sharing.

All existing projection and real Chromium tests still run. Dependency audits,
read-only permissions, role coverage and application source are unchanged.
There is no change to model policy, data selection, or production deployment.

Official image documentation: https://playwright.dev/docs/docker

Validation: actual workflow checks are required before merge. Release evidence
and the larger analysis-feature rollout are tracked on
docs/analysis-evidence-release-20261111.
