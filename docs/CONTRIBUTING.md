# Contributing Guide

## Pull request policy

### No binary assets in PRs
- Every pull request must stay text-only. Do not add images, fonts, archives, or other binary blobs to the repository history.
- Visual assets should be published via the CDN or handled through a separate Git LFS process that does not touch the main repo.
- UI artifacts such as previews or screenshots are generated in CI and uploaded as build artifacts only, never committed.
