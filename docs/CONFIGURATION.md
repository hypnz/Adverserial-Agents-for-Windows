# Configuration and dynamic paths

Setup writes `local-config.json` into the repository root. Keep that file private
and local: it is ignored by Git and excluded from source releases.

The runtime resolves relative paths from the adapter root, not the terminal's
current directory. It supports `${USERPROFILE}`, `${LOCALAPPDATA}`, `${HOME}`,
`${ADAPTER_ROOT}` and environment variables in `${NAME}` or `%NAME%` form.
Unknown variables are rejected. Use JSON strings with forward slashes to avoid
backslash escaping problems.

A minimal example after installing the kit runtime is:

```json
{
  "configVersion": 2,
  "kitDir": "${USERPROFILE}/adverserial-kit-hermes",
  "nodeBinary": "auto",
  "hermesBin": "auto",
  "hermesDir": "${LOCALAPPDATA}/hermes/hermes-agent"
}
```

This is a reference, not a replacement for running setup. The kit folder must
already contain the pinned resources and its installed `.venv-hermes` runtime.
Non-Hermes launch targets do not require a Hermes installation.

SDK, Python and hardware-verifier paths are derived from the selected kit folder
at each launch. New setup may retain those fields for compatibility, but the
resolver recomputes them. `nodeBinary: "auto"` uses Node from PATH. Hermes is
rediscovered from PATH or the configured repository when needed.

A sibling kit can use `"kitDir": "../adverserial-kit-hermes"`. An adapter-local
kit can use `"kitDir": "./adverserial-kit-hermes"`. A kit on a separate drive
may require an explicit drive path; no resolver can infer that arbitrary location.
Discovery checks configured and a small set of conventional paths, not the whole
disk. Old `C:/Users/<old-user>/...` paths are rebased to the current user in memory.

## Agent binaries

For nonstandard launchers use `run.py AGENT --agent-bin PATH`, or environment
variables such as ADVERSERIAL_CODEX_BIN, ADVERSERIAL_PI_BIN, ADVERSERIAL_OMP_BIN
and ADVERSERIAL_DSH_BIN. ACK_<BINARY>_BIN overrides are also accepted.
Explicit relative paths are adapter-root-relative. Agent inventory may not
report an unusual Hermes install absent from PATH; its dedicated launch path can
still use the Hermes location stored by setup.

## Profiles and workspaces

`--profile` accepts 1–64 letters, digits, underscores or hyphens. Hermes and other
agents have distinct profile roots; see INSTALL_WINDOWS.md. A profile is owned
by at most one active launch. Use different profiles for concurrent sessions.
`--workspace` selects the working directory and must point to an existing folder.
The default workspace is the terminal's current directory.

Only model IDs supported by the adapter are accepted: lordx64/cyberglm and
lordx64/cyberkimi. Availability still depends on an active published policy.
The client context value 1048576 follows the kit's Hermes/reference configuration;
it is not a guarantee that every model accepts a maximum-size inference.
