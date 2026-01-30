# Release Workflow Setup

## To create a new release:

1. Update the version number in your code (optional, depending on your versioning approach)
2. Commit and push your changes to the main branch
3. Create a new tag with the format `vX.Y.Z` (e.g., `v1.0.0`, `v1.2.1`)
4. Push the tag to GitHub: `git push origin vX.Y.Z`

The GitHub Actions workflow will automatically:
- Create a new release on GitHub
- Package the source code
- Upload the packaged source code as a release asset

## Available Workflows:

- `source-release.yml`: Creates releases with source code packages
- `release.yml`: Creates basic releases with zipped source code
- `build-release.yml`: Creates releases with platform-specific executables

## Version Tag Format:
Tags should follow semantic versioning: `vX.Y.Z` where:
- X is the major version
- Y is the minor version  
- Z is the patch version

Example: v1.0.0, v1.2.3, v2.0.0