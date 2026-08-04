# Keep API secrets in a local .env file

The local CLI reads API secrets only from a workspace-root `.env` file that is excluded from Git, permissioned to the local user, never copied into Trip workspaces or exports, and never logged. A committed `.env.example` contains names only, and a small built-in loader avoids adding a dependency solely for configuration.
